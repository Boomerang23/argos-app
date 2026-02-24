from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from . import models, schemas, database, auth
from .auth import create_access_token
from .database import SessionLocal, engine
from .services import ScreeningService, log_action
from sqlalchemy.exc import IntegrityError
from datetime import datetime

# --- PASSWORD HASHING ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)



models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="ARGOS 360 - Compliance Platform",
    description="Enterprise AML/KYC compliance platform",
    version="1.0.0",
)

@app.get("/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": current_user.organization_id,
        "is_active": current_user.is_active,
    }

@app.get("/organizations/", response_model=list[schemas.OrganizationOut])
def list_organizations(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    return db.query(models.Organization).order_by(models.Organization.id.desc()).all()


@app.post("/organizations/", response_model=schemas.OrganizationOut)
def create_organization(
    payload: schemas.OrganizationCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    existing = db.query(models.Organization).filter(models.Organization.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Organization already exists")

    org = models.Organization(name=payload.name)
    db.add(org)
    db.commit()
    db.refresh(org)

    log_action(db, current_user, action="ORG_CREATE", target=str(org.id), details=f"name={org.name}")
    return org


@app.post("/organizations/create-admin")
def create_tenant_admin(
    payload: schemas.TenantAdminCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == payload.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    exists = db.query(models.User).filter(models.User.email == payload.admin_email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email already exists (global)")

    hashed_pwd = get_password_hash(payload.password)

    user = models.User(
        organization_id=org.id,
        email=payload.admin_email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name,
        role="ADMIN",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log_action(
        db,
        current_user,
        action="TENANT_ADMIN_CREATE",
        target=user.email,
        details=f"org_id={org.id} org_name={org.name}",
    )

    return {"status": "success", "org_id": org.id, "admin_email": user.email}

@app.get("/organizations/{org_id}/users", response_model=list[schemas.UserOut])
def list_org_users(
    org_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    return (
        db.query(models.User)
        .filter(models.User.organization_id == org_id)
        .order_by(models.User.id.desc())
        .all()
    )


@app.post("/organizations/{org_id}/users", response_model=schemas.UserOut)
def create_org_user(
    org_id: int,
    payload: schemas.OrgUserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # sécurité: interdire création SUPER_ADMIN via API
    role = (payload.role or "AGENT").upper()
    if role not in {"ADMIN", "AGENT"}:
        raise HTTPException(status_code=400, detail="role must be ADMIN or AGENT")

    # email unique global
    exists = db.query(models.User).filter(models.User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Cet email existe déjà (global).")

    hashed_pwd = get_password_hash(payload.password)

    user = models.User(
        organization_id=org_id,
        email=payload.email,
        hashed_password=hashed_pwd,
        full_name=payload.full_name,
        role=role,
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email déjà utilisé.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    log_action(
        db,
        current_user,
        action="ORG_USER_CREATE",
        target=user.email,
        details=f"org_id={org_id} role={role}",
    )

    return user

@app.get("/")
def read_root():
    return {"status": "active", "system": "ARGOS 360", "mode": "enterprise"}


# --- AUTH / TOKEN ---
@app.post("/token")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Identifiants incorrects")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Compte désactivé")

    access_token = create_access_token(
        subject=user.email,
        extra_claims={
            "role": user.role,
            "user_id": user.id,
            "organization_id": user.organization_id,
        },
    )

    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


# --- CLIENTS (TENANT-SCOPED) ---
@app.post("/clients/")
def create_or_verify_client(
    client: schemas.ClientCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    # chercher uniquement dans le tenant
    db_client = (
        db.query(models.Client)
        .filter(
            models.Client.organization_id == current_user.organization_id,
            models.Client.national_id == client.national_id,
        )
        .first()
    )

    if db_client:
        db_client.full_name = client.full_name
        db_client.entity_type = client.entity_type
        db_client.country_residence = client.country_residence
        db_client.tenant_id = client.tenant_id
    else:
        db_client = models.Client(
            organization_id=current_user.organization_id,
            **client.dict()
        )
        db.add(db_client)

    db.commit()
    db.refresh(db_client)

    # screening
    screening_service = ScreeningService()
    matches = screening_service.check_name(db, client.full_name,
    organization_id=current_user.organization_id)

    db_hist = models.ScanHistory(
    organization_id=current_user.organization_id,
    date=datetime.utcnow().isoformat(),
    client_name=client.full_name,
    status="MATCH" if matches else "CLEAR",
    details="MATCH_FOUND" if matches else "NO_MATCH",
    )
    db.add(db_hist)
    db.commit()



    log_action(
        db,
        current_user,
        action="CLIENT_SCAN",
        target=client.national_id,
        details=f"name={client.full_name}",
    )

    if matches:
        best_match = matches[0]
        matched_name = best_match["matched_name"]
        score = best_match.get("score", 100)
        source = best_match.get("list_source", "Watchlist")

        if score >= 80:
            new_alert = models.Alert(
                organization_id=current_user.organization_id,
                client_name=client.full_name,
                matched_name=matched_name,
                similarity_score=score,
                status="OUVERT",
                assigned_to="Non assigné",
            )
            db.add(new_alert)
            db.commit()
            db.refresh(new_alert)

            log_action(
                db,
                current_user,
                action="ALERT_CREATE",
                target=str(new_alert.id),
                details=f"client={client.full_name} matched={matched_name} score={score} source={source}",
            )

        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "ELEVE",
            "similarity_score": score,
            "details": f"🚨 ALERTE (Similitude : {score}%) - Correspondance avec '{matched_name}' (Source : {source})",
        }

    return {
        "id": db_client.id,
        "full_name": db_client.full_name,
        "national_id": db_client.national_id,
        "risk_score": "FAIBLE",
        "similarity_score": 0,
        "details": "✅ RAS - Aucune correspondance significative",
    }


# --- SANCTIONS (AGENT + ADMIN) (TENANT-SCOPED) ---
@app.post("/sanctions/")
def add_sanction(
    sanction: schemas.SanctionCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    doublon = (
        db.query(models.Sanction)
        .filter(
            models.Sanction.organization_id == current_user.organization_id,
            models.Sanction.name == sanction.name,
            models.Sanction.list_source == sanction.list_source,
        )
        .first()
    )

    if doublon:
        return {"status": "skipped", "message": "Doublon ignoré", "name": sanction.name}

    db_sanction = models.Sanction(
        organization_id=current_user.organization_id,
        **sanction.dict()
    )
    db.add(db_sanction)
    db.commit()
    db.refresh(db_sanction)

    log_action(
        db,
        current_user,
        action="SANCTION_ADD",
        target=db_sanction.id,
        details=f"name={db_sanction.name} source={db_sanction.list_source}",
    )

    return {"status": "success", "name": db_sanction.name}


@app.get("/sanctions/view")
def get_sanctions_by_list(
    list_name: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.Sanction)
        .filter(
            models.Sanction.organization_id == current_user.organization_id,
            models.Sanction.list_source == list_name,
        )
        .all()
    )


# --- SCREENING CHECK (TENANT-SCOPED sanctions inside service; still logs per tenant) ---
@app.post("/screening/check", response_model=schemas.ScreeningResult)
def screen_name(
    request: schemas.ScreeningRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    service = ScreeningService()
    matches = service.check_name(db, request.name,
    organization_id=current_user.organization_id)

    risk = "FAIBLE"
    if matches:
        risk = "ELEVE"

    log_action(
        db,
        current_user,
        action="SCREENING_CHECK",
        target=request.name,
        details=f"risk={risk}",
    )

    return {"input_name": request.name, "matches": matches, "risk_level": risk}


# --- ADMIN: SANCTIONS DEDUP (TENANT-SCOPED) ---
@app.delete("/sanctions/duplicates")
def clean_duplicates(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    sanctions = (
        db.query(models.Sanction)
        .filter(models.Sanction.organization_id == current_user.organization_id)
        .all()
    )

    vus = set()
    doublons_supprimes = 0

    for s in sanctions:
        cle = (s.name.strip().lower(), s.list_source)
        if cle in vus:
            db.delete(s)
            doublons_supprimes += 1
        else:
            vus.add(cle)

    db.commit()

    log_action(
        db,
        current_user,
        action="SANCTIONS_DEDUP",
        target="sanctions",
        details=f"deleted_count={doublons_supprimes}",
    )

    return {"status": "success", "deleted_count": doublons_supprimes}


# --- LOGS (TENANT-SCOPED) ---
@app.get("/logs/")
def get_logs(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.AuditLog)
        .filter(models.AuditLog.organization_id == current_user.organization_id)
        .order_by(models.AuditLog.id.desc())
        .all()
    )


# --- HISTORY (left as-is; optional to tenant-scope later) ---
@app.get("/history/")
def get_history(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.ScanHistory)
        .filter(models.ScanHistory.organization_id == current_user.organization_id)
        .order_by(models.ScanHistory.id.desc())
        .all()
    )


# --- LISTS (TENANT-SCOPED) ---
@app.post("/lists/")
def create_list(
    lst: schemas.CustomListCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    exists = (
        db.query(models.CustomList)
        .filter(
            models.CustomList.organization_id == current_user.organization_id,
            models.CustomList.name == lst.name,
        )
        .first()
    )
    if exists:
        return {"status": "skipped", "message": "Liste déjà existante", "name": lst.name}

    db_lst = models.CustomList(
        name=lst.name,
        organization_id=current_user.organization_id,
    )
    db.add(db_lst)
    db.commit()

    log_action(
        db,
        current_user,
        action="LIST_CREATE",
        target=lst.name,
        details="",
    )

    return {"status": "ok"}


@app.get("/lists/")
def get_lists(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.CustomList)
        .filter(models.CustomList.organization_id == current_user.organization_id)
        .all()
    )


@app.delete("/lists/{list_name}")
def delete_list(
    list_name: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    try:
        # delete sanctions for this org + list
        noms_supprimes = (
            db.query(models.Sanction)
            .filter(
                models.Sanction.organization_id == current_user.organization_id,
                models.Sanction.list_source == list_name,
            )
            .delete(synchronize_session=False)
        )

        db_lst = (
            db.query(models.CustomList)
            .filter(
                models.CustomList.organization_id == current_user.organization_id,
                models.CustomList.name == list_name,
            )
            .first()
        )
        if db_lst:
            db.delete(db_lst)

        db.commit()

        log_action(
            db,
            current_user,
            action="LIST_DELETE",
            target=list_name,
            details=f"sanctions_deleted={noms_supprimes}",
        )

        return {
            "status": "success",
            "message": "Liste et noms associés supprimés avec succès.",
            "noms_effaces": noms_supprimes,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- USERS (ADMIN ONLY; tenant-scoped) ---
@app.post("/users/", response_model=schemas.UserOut)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    # ✅ check GLOBAL (car email est unique globalement en DB)
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Cet email existe déjà (global).")

    hashed_pwd = get_password_hash(user.password)

    new_user = models.User(
        organization_id=current_user.organization_id,
        email=user.email,
        hashed_password=hashed_pwd,
        full_name=user.full_name,
        role=user.role,
        is_active=True,
    )

    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email déjà utilisé.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    log_action(
        db,
        current_user,
        action="USER_CREATE",
        target=new_user.email,
        details=f"role={new_user.role}",
    )

    return new_user

@app.get("/users/")
def get_users(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    return (
        db.query(models.User)
        .filter(models.User.organization_id == current_user.organization_id)
        .all()
    )


# --- STARTUP: create Default Org + Admin ---
@app.on_event("startup")
def create_admin_user():
    db = SessionLocal()
    models.Base.metadata.create_all(bind=engine)

    # 1) Créer / garantir l'existence de Default Org
    org = db.query(models.Organization).filter(models.Organization.name == "Default Org").first()
    if not org:
        org = models.Organization(name="Default Org")
        db.add(org)
        db.commit()
        db.refresh(org)

    # 2) Créer / garantir l'existence du compte plateforme (SUPER_ADMIN global)
    user = db.query(models.User).filter(models.User.email == "admin@sgi.ci").first()

    if not user:
        hashed_password = get_password_hash("admin")
        user = models.User(
            organization_id=None,  # ✅ GLOBAL
            email="admin@sgi.ci",
            hashed_password=hashed_password,
            full_name="Super Administrateur",
            role="SUPER_ADMIN",
            is_active=True,
        )
        db.add(user)
        db.commit()
    else:
        # ✅ Si déjà existant, on force le mode plateforme
        user.role = "SUPER_ADMIN"
        user.organization_id = None
        user.is_active = True
        db.commit()

    db.close()

# --- ALERTS (TENANT-SCOPED + Maker/Checker) ---
@app.get("/alerts/", response_model=list[schemas.AlertOut])
def get_alerts(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.Alert)
        .filter(models.Alert.organization_id == current_user.organization_id)
        .order_by(models.Alert.created_at.desc())
        .all()
    )


@app.patch("/alerts/{alert_id}")
def update_alert(
    alert_id: int,
    update_data: schemas.AlertUpdate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    db_alert = (
        db.query(models.Alert)
        .filter(
            models.Alert.organization_id == current_user.organization_id,
            models.Alert.id == alert_id,
        )
        .first()
    )
    if not db_alert:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    is_admin = current_user.role == "ADMIN"

    # AGENT: interdit de décider + interdit de fermer
    if not is_admin:
        if getattr(update_data, "decision", None) is not None:
            raise HTTPException(status_code=403, detail="Admin required to set decision")

        if getattr(update_data, "status", None) in {"FERME", "CLOSED"}:
            raise HTTPException(status_code=403, detail="Admin required to close alerts")

    for var, value in update_data.dict(exclude_unset=True).items():
        setattr(db_alert, var, value)

    db.commit()

    log_action(
        db,
        current_user,
        action="ALERT_UPDATE",
        target=str(alert_id),
        details=f"fields={list(update_data.dict(exclude_unset=True).keys())}",
    )

    return {"status": "success", "message": f"Alerte {alert_id} mise à jour"}