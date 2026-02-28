# =========================
# main.py (BLOC 1/5)
# Imports + App + Auth
# =========================
from dotenv import load_dotenv

load_dotenv()

import os
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, status, Response, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from sqlalchemy.exc import IntegrityError

from . import models, schemas, database, auth
from .database import SessionLocal, engine
from .services import ScreeningService, log_action


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
    version="2.0.0",
)

# ---------------------------
# CORS (OBLIGATOIRE POUR COOKIE)
# ---------------------------
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# JWT Cookie Config
# ---------------------------
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "argos_refresh")
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")  # ex ".argos360.com" en prod

# ==========================================================
# ✅ API V1 ROUTER
# ==========================================================
api_v1 = APIRouter(prefix="/api/v1")

# ---------------------------
# AUTH ENDPOINTS
# ---------------------------
@app.post("/api/v1/auth/login")
def login_api(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants incorrects",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Compte désactivé")

    access_token = auth.create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role,
            "organization_id": user.organization_id,
            "email": user.email,
        },
    )

    refresh_token = auth.create_refresh_token(
        subject=str(user.id),
        extra_claims={"organization_id": user.organization_id},
    )

    # cookie refresh
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        domain=COOKIE_DOMAIN,
        path="/api/v1/auth/refresh",
        max_age=60 * 60 * 24 * REFRESH_TOKEN_EXPIRE_DAYS,
    )

    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


@app.post("/api/v1/auth/refresh")
def refresh_api(request: Request, db: Session = Depends(database.get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing refresh cookie")

    payload = auth.decode_refresh_token(token)
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.query(models.User).filter(models.User.id == int(sub)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid user")

    access_token = auth.create_access_token(
        subject=str(user.id),
        extra_claims={
            "role": user.role,
            "organization_id": user.organization_id,
            "email": user.email,
        },
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/v1/auth/logout")
def logout_api(response: Response):
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/api/v1/auth/refresh",
        domain=COOKIE_DOMAIN,
    )
    return {"ok": True}


@app.get("/api/v1/auth/me")
def me_api(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "is_active": current_user.is_active,
        },
        "organization": {
            "id": current_user.organization_id,
        },
    }


# Healthcheck public
@app.get("/")
def read_root():
    return {"status": "active", "system": "ARGOS 360", "mode": "enterprise"}


# Compat (tu pourras le supprimer plus tard)
@app.get("/me")
def me(current_user: models.User = Depends(auth.get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "role": current_user.role,
        "organization_id": current_user.organization_id,
        "is_active": current_user.is_active,
    }
# =========================
# main.py (BLOC 2/5)
# Organizations (SUPER_ADMIN)
# =========================

@api_v1.get("/organizations/", response_model=list[schemas.OrganizationOut])
def list_organizations(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    return db.query(models.Organization).order_by(models.Organization.id.desc()).all()


@api_v1.post("/organizations/", response_model=schemas.OrganizationOut)
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


@api_v1.post("/organizations/create-admin")
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


@api_v1.get("/organizations/{org_id}/users", response_model=list[schemas.UserOut])
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


@api_v1.post("/organizations/{org_id}/users", response_model=schemas.UserOut)
def create_org_user(
    org_id: int,
    payload: schemas.OrgUserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_super_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    role = (payload.role or "AGENT").upper()
    if role not in {"ADMIN", "AGENT"}:
        raise HTTPException(status_code=400, detail="role must be ADMIN or AGENT")

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
# =========================
# main.py (BLOC 3/5)
# Clients + Sanctions + Screening
# =========================

@api_v1.post("/clients/")
def create_or_verify_client(
    client: schemas.ClientCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if current_user.organization_id is None:
        raise HTTPException(
            status_code=400,
            detail="Super admin must select an organization before creating clients.",
        )

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
        db_client = models.Client(organization_id=current_user.organization_id, **client.dict())
        db.add(db_client)

    db.commit()
    db.refresh(db_client)

    screening_service = ScreeningService()
    matches = screening_service.check_name(db, client.full_name, organization_id=current_user.organization_id)

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
                decision=None,
                comments=None,
                assigned_user_id=None,
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
                "details": f" ALERTE (Similitude : {score}%) - Correspondance avec '{matched_name}' (Source : {source})",
            }

    return {
        "id": db_client.id,
        "full_name": db_client.full_name,
        "national_id": db_client.national_id,
        "risk_score": "FAIBLE",
        "similarity_score": 0,
        "details": "✅ RAS - Aucune correspondance significative",
    }


@api_v1.get("/clients/")
def list_clients(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    rows = (
        db.query(models.Client)
        .filter(models.Client.organization_id == current_user.organization_id)
        .order_by(models.Client.created_at.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "full_name": c.full_name,
            "national_id": c.national_id,
            "risk_score": c.risk_score,
        }
        for c in rows
    ]


@api_v1.post("/sanctions/")
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

    db_sanction = models.Sanction(organization_id=current_user.organization_id, **sanction.dict())
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


@api_v1.get("/sanctions/view")
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


@api_v1.post("/screening/check", response_model=schemas.ScreeningResult)
def screen_name(
    request: schemas.ScreeningRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    service = ScreeningService()
    matches = service.check_name(db, request.name, organization_id=current_user.organization_id)

    risk = "FAIBLE"
    if matches:
        risk = "ELEVE"

    log_action(db, current_user, action="SCREENING_CHECK", target=request.name, details=f"risk={risk}")
    return {"input_name": request.name, "matches": matches, "risk_level": risk}


@api_v1.delete("/sanctions/duplicates")
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
    deleted_count = 0
    for s in sanctions:
        cle = (s.name.strip().lower(), s.list_source)
        if cle in vus:
            db.delete(s)
            deleted_count += 1
        else:
            vus.add(cle)

    db.commit()

    log_action(
        db,
        current_user,
        action="SANCTIONS_DEDUP",
        target="sanctions",
        details=f"deleted_count={deleted_count}",
    )
    return {"status": "success", "deleted_count": deleted_count}
# =========================
# main.py (BLOC 4/5)
# Logs + History + Lists + Users(tenant)
# =========================

@api_v1.get("/logs/")
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


@api_v1.get("/history/")
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


@api_v1.post("/lists/")
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

    db_lst = models.CustomList(name=lst.name, organization_id=current_user.organization_id)
    db.add(db_lst)
    db.commit()

    log_action(db, current_user, action="LIST_CREATE", target=lst.name, details="")
    return {"status": "ok"}


@api_v1.get("/lists/")
def get_lists(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    return (
        db.query(models.CustomList)
        .filter(models.CustomList.organization_id == current_user.organization_id)
        .all()
    )


@api_v1.delete("/lists/{list_name}")
def delete_list(
    list_name: str,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    try:
        sanctions_deleted = (
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
            details=f"sanctions_deleted={sanctions_deleted}",
        )

        return {
            "status": "success",
            "message": "Liste et noms associés supprimés avec succès.",
            "noms_effaces": sanctions_deleted,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@api_v1.post("/users/", response_model=schemas.UserOut)
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
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

    log_action(db, current_user, action="USER_CREATE", target=new_user.email, details=f"role={new_user.role}")
    return new_user


@api_v1.get("/users/")
def get_users(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_admin),
):
    return (
        db.query(models.User)
        .filter(models.User.organization_id == current_user.organization_id)
        .all()
    )
# =========================
# main.py (BLOC 5/5)
# Alerts + Events + include_router + startup
# =========================

@api_v1.get("/alerts/", response_model=list[schemas.AlertOut])
def get_alerts(
    status: Optional[str] = None,
    decision: Optional[str] = None,
    q: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    assigned: Optional[str] = None,  # "me"
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    query = db.query(models.Alert).filter(models.Alert.organization_id == current_user.organization_id)

    # Filtre assignment "me"
    if assigned and assigned.strip().lower() == "me":
        query = query.filter(models.Alert.assigned_user_id == current_user.id)

    # Filtre assignment par user (ADMIN)
    if assigned_user_id is not None:
        if current_user.role != "ADMIN":
            raise HTTPException(status_code=403, detail="Admin required to filter by assignee")
        query = query.filter(models.Alert.assigned_user_id == assigned_user_id)

    # Filtre statut
    if status:
        st = status.strip().upper()
        if st == "CLOSED":
            st = "FERME"
        query = query.filter(models.Alert.status == st)

    # Filtre décision
    if decision:
        dec = decision.strip().upper()
        query = query.filter(models.Alert.decision == dec)

    # Recherche
    if q:
        qq = q.strip()
        if qq:
            like = f"%{qq}%"
            if qq.isdigit():
                query = query.filter(
                    (models.Alert.id == int(qq))
                    | (models.Alert.client_name.ilike(like))
                    | (models.Alert.matched_name.ilike(like))
                )
            else:
                query = query.filter(
                    (models.Alert.client_name.ilike(like))
                    | (models.Alert.matched_name.ilike(like))
                )

    return query.order_by(models.Alert.created_at.desc()).all()


@api_v1.patch("/alerts/{alert_id}")
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

    # AGENT peut seulement s'assigner lui-même
    if update_data.assigned_user_id is not None:
        if (not is_admin) and (update_data.assigned_user_id != current_user.id):
            raise HTTPException(status_code=403, detail="Cannot assign to another user")

    # décision + fermeture réservées à ADMIN
    if not is_admin:
        if update_data.decision is not None:
            raise HTTPException(status_code=403, detail="Admin required to set decision")
        if update_data.status is not None and str(update_data.status).upper() in {"FERME", "CLOSED"}:
            raise HTTPException(status_code=403, detail="Admin required to close alerts")

    def create_event(event_type: str, old_value: Optional[str], new_value: Optional[str]):
        evt = models.AlertEvent(
            alert_id=db_alert.id,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            user_email=current_user.email,
            event_type=event_type,
            old_value=old_value,
            new_value=new_value,
        )
        db.add(evt)

    payload = update_data.dict(exclude_unset=True)

    # ✅ normalisation simple
    if "status" in payload and payload["status"] is not None:
        st = str(payload["status"]).upper().strip()
        if st == "CLOSED":
            st = "FERME"
        payload["status"] = st

    if "decision" in payload and payload["decision"] is not None:
        payload["decision"] = str(payload["decision"]).upper().strip()

    for var, value in payload.items():
        # Option: on ignore assigned_to (legacy) dans la timeline
        if var == "assigned_to":
            setattr(db_alert, var, value)
            continue

        old = getattr(db_alert, var, None)

        # ✅ pas d'event si pas de changement réel
        if old == value:
            continue

        setattr(db_alert, var, value)

        if var == "assigned_user_id":
            create_event(
                "ASSIGNED",
                str(old) if old is not None else None,
                str(value) if value is not None else None,
            )
        elif var == "status":
            create_event(
                "STATUS_CHANGE",
                str(old) if old is not None else None,
                str(value) if value is not None else None,
            )
        elif var == "decision":
            create_event(
                "DECISION",
                str(old) if old is not None else None,
                str(value) if value is not None else None,
            )
        elif var == "comments":
            create_event(
                "COMMENT",
                str(old) if old is not None else None,
                str(value) if value is not None else None,
            )

    # Fermeture => closed_at + event CLOSED
    if "status" in payload and payload["status"] is not None:
        new_status = str(payload["status"]).upper()
        if new_status == "FERME":
            if db_alert.closed_at is None:
                create_event("CLOSED", None, "FERME")
            db_alert.closed_at = datetime.utcnow()
        else:
            db_alert.closed_at = None

    db.commit()
    db.refresh(db_alert)

    log_action(
        db,
        current_user,
        action="ALERT_UPDATE",
        target=str(alert_id),
        details=f"fields={list(payload.keys())}",
    )

    return {"status": "success", "message": f"Alerte {alert_id} mise à jour"}

@api_v1.get("/alerts/{alert_id}/events", response_model=list[schemas.AlertEventOut])
def get_alert_events(
    alert_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(auth.require_agent_or_admin),
):
    exists = (
        db.query(models.Alert)
        .filter(
            models.Alert.organization_id == current_user.organization_id,
            models.Alert.id == alert_id,
        )
        .first()
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")

    return (
        db.query(models.AlertEvent)
        .filter(
            models.AlertEvent.organization_id == current_user.organization_id,
            models.AlertEvent.alert_id == alert_id,
        )
        .order_by(models.AlertEvent.created_at.desc())
        .all()
    )


# ✅ include router
app.include_router(api_v1)


# --- STARTUP: create Default Org + Super Admin ---
@app.on_event("startup")
def create_admin_user():
    db = SessionLocal()
    models.Base.metadata.create_all(bind=engine)

    org = db.query(models.Organization).filter(models.Organization.name == "Default Org").first()
    if not org:
        org = models.Organization(name="Default Org")
        db.add(org)
        db.commit()
        db.refresh(org)

    user = db.query(models.User).filter(models.User.email == "admin@sgi.ci").first()
    if not user:
        hashed_password = get_password_hash("admin")
        user = models.User(
            organization_id=None,
            email="admin@sgi.ci",
            hashed_password=hashed_password,
            full_name="Super Administrateur",
            role="SUPER_ADMIN",
            is_active=True,
        )
        db.add(user)
        db.commit()
    else:
        user.role = "SUPER_ADMIN"
        user.organization_id = None
        user.is_active = True
        db.commit()

    db.close()