from fastapi import FastAPI, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, schemas, database, auth
from .database import SessionLocal, engine
from passlib.context import CryptContext

# --- MOTEUR DE SÉCURITÉ (CRYPTAGE) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


# Création automatique des tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="SaaS AML SGI - Côte d'Ivoire",
    description="API de lutte contre le blanchiment d'argent pour les SGIs (Conforme UEMOA)",
    version="1.0.0"
)

# Health Check
@app.get("/")
def read_root():
    return {"status": "active", "system": "AML Core", "compliance_zone": "UEMOA"}

# --- ROUTE CONNEXION (Pour obtenir le jeton) ---
@app.post("/token")
def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(database.get_db)):
    # 1. Le compte de secours (Pour ne jamais que tu sois bloqué hors du système)
    if username == "admin@sgi.ci" and password == "admin":
        return {"access_token": "super_admin_token", "token_type": "bearer", "role": "ADMIN"}

    # 2. Chercher le vrai utilisateur dans Neon
    user = db.query(models.User).filter(models.User.email == username).first()
    
    # 3. Vérifier si l'utilisateur existe ET si le mot de passe crypté correspond
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Identifiants incorrects")

    # 4. Vérifier si le compte n'a pas été désactivé
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Ce compte a été désactivé")

    return {"access_token": f"user_{user.id}_token", "token_type": "bearer", "role": user.role}


# --- ROUTES CLIENTS & SCREENING ---
@app.post("/clients/")
def create_or_verify_client(client: schemas.ClientCreate, db: Session = Depends(database.get_db)):
    
    # 1. Enregistrement ou mise à jour du client scanné
    db_client = db.query(models.Client).filter(models.Client.national_id == client.national_id).first()
    if db_client:
        db_client.full_name = client.full_name
    else:
        db_client = models.Client(**client.dict())
        db.add(db_client)
        
    db.commit()
    db.refresh(db_client)

    # 2. Le Screening
    from .services import ScreeningService
    screening_service = ScreeningService()
    matches = screening_service.check_name(db, client.full_name)
        
   # 3. La Réponse Personnalisée & Création d'Alerte
    if matches:
        best_match = matches[0]
        criminel_trouve = best_match['matched_name']
        score = best_match.get('score', 100)
        liste_origine = best_match.get('list_source', 'Liste de Surveillance')
        
        # NOUVEAU : Création automatique d'un ticket d'alerte dans la base de données
        if score >= 80:
            new_alert = models.Alert(
                client_name=client.full_name,
                matched_name=criminel_trouve,
                similarity_score=score,
                status="OUVERT",
                assigned_to="Non assigné"
            )
            db.add(new_alert)
            db.commit()

        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "ELEVE",
            "similarity_score": score,
            "details": f"🚨 ALERTE (Similitude : {score}%) - Correspondance avec '{criminel_trouve}' (Source : {liste_origine})"
        }
    else:
        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "FAIBLE",
            "similarity_score": 0, # <-- NOUVEAU : Score à 0 si tout va bien
            "details": "✅ RAS - Aucune correspondance significative"
        }

# --- CORRECTION : BOUCLIER ANTI-DOUBLONS ---
@app.post("/sanctions/")
def add_sanction(sanction: schemas.SanctionCreate, db: Session = Depends(database.get_db)):
    # 1. On vérifie si le nom existe déjà DANS LA MÊME LISTE
    doublon = db.query(models.Sanction).filter(
        models.Sanction.name == sanction.name,
        models.Sanction.list_source == sanction.list_source
    ).first()

    if doublon:
        # On renvoie un statut "skipped" pour que le frontend comprenne que c'est ignoré sans planter
        return {"status": "skipped", "message": "Doublon ignoré", "name": sanction.name}

    # 2. Si pas de doublon, on enregistre
    try:
        db_sanction = models.Sanction(**sanction.dict())
        db.add(db_sanction)
        db.commit()
        db.refresh(db_sanction)
        return {"status": "success", "name": db_sanction.name}
    except Exception as e:
        db.rollback() 
        raise HTTPException(status_code=400, detail="Format invalide ou erreur base de données.")

# --- AJOUT : Route pour lire le contenu d'une liste ---
@app.get("/sanctions/view")
def get_sanctions_by_list(list_name: str, db: Session = Depends(database.get_db)):
    """Récupère toutes les entrées d'une liste spécifique pour affichage"""
    items = db.query(models.Sanction).filter(models.Sanction.list_source == list_name).all()
    return items
    
from .services import ScreeningService

@app.post("/screening/check", response_model=schemas.ScreeningResult)
def screen_name(request: schemas.ScreeningRequest, db: Session = Depends(database.get_db)): 
    service = ScreeningService()
    matches = service.check_name(db, request.name)
    
    risk = "FAIBLE"
    if matches:
        risk = "ELEVE"
        
    return {
        "input_name": request.name,
        "matches": matches,
        "risk_level": risk
    }

# --- OUTIL DE NETTOYAGE DES DOUBLONS ---
@app.delete("/sanctions/duplicates")
def clean_duplicates(db: Session = Depends(database.get_db)):
    """Parcourt la base de données et supprime tous les doublons exacts."""
    sanctions = db.query(models.Sanction).all()
    vus = set()
    doublons_supprimes = 0
    
    for s in sanctions:
        # On crée une clé unique (Nom en minuscules + Liste source)
        cle = (s.name.strip().lower(), s.list_source)
        
        if cle in vus:
            # Si on l'a déjà vu, c'est un doublon, on le supprime !
            db.delete(s)
            doublons_supprimes += 1
        else:
            # Sinon, on l'ajoute à notre mémoire
            vus.add(cle)
            
    db.commit()
    return {"status": "success", "deleted_count": doublons_supprimes}

# --- ROUTES POUR L'HISTORIQUE ET LES LOGS CLOUD ---
@app.post("/logs/")
def create_log(log: schemas.AuditLogCreate, db: Session = Depends(database.get_db)):
    db_log = models.AuditLog(**log.dict())
    db.add(db_log)
    db.commit()
    return {"status": "ok"}

@app.get("/logs/")
def get_logs(db: Session = Depends(database.get_db)):
    return db.query(models.AuditLog).order_by(models.AuditLog.id.desc()).all()

@app.post("/history/")
def create_history(hist: schemas.ScanHistoryCreate, db: Session = Depends(database.get_db)):
    db_hist = models.ScanHistory(**hist.dict())
    db.add(db_hist)
    db.commit()
    return {"status": "ok"}

@app.get("/history/")
def get_history(db: Session = Depends(database.get_db)):
    return db.query(models.ScanHistory).all()

@app.post("/lists/")
def create_list(lst: schemas.CustomListCreate, db: Session = Depends(database.get_db)):
    db_lst = models.CustomList(name=lst.name)
    db.add(db_lst)
    db.commit()
    return {"status": "ok"}

@app.get("/lists/")
def get_lists(db: Session = Depends(database.get_db)):
    return db.query(models.CustomList).all()

@app.delete("/lists/{list_name}")
def delete_list(list_name: str, db: Session = Depends(database.get_db)):
    try:
        # 1. LE GRAND NETTOYAGE : Supprime tous les noms associés à cette liste dans la table Sanction
        noms_supprimes = db.query(models.Sanction).filter(models.Sanction.list_source == list_name).delete(synchronize_session=False)
        
        # 2. Supprime l'étiquette de la liste dans la table CustomList
        db_lst = db.query(models.CustomList).filter(models.CustomList.name == list_name).first()
        if db_lst:
            db.delete(db_lst)
            
        # 3. On valide toutes les suppressions d'un coup
        db.commit()
        
        return {
            "status": "success", 
            "message": "Liste et noms associés supprimés avec succès.",
            "noms_effaces": noms_supprimes
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- ROUTES UTILISATEURS ---
@app.post("/users/", response_model=schemas.UserOut)
def create_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # Vérifier si l'email existe déjà dans la base
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Cet email existe déjà.")

    # Crypter le mot de passe avant sauvegarde
    hashed_pwd = get_password_hash(user.password)
    
    new_user = models.User(
        email=user.email,
        hashed_password=hashed_pwd,
        full_name=user.full_name,
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.get("/users/")
def get_users(db: Session = Depends(database.get_db)):
    return db.query(models.User).all()


# --- INITIALISATION AUTOMATIQUE ---
@app.on_event("startup")
def create_admin_user():
    db = SessionLocal()
    # On crée les tables si elles n'existent pas
    models.Base.metadata.create_all(bind=engine)
    
    # On vérifie si l'admin existe déjà
    user = db.query(models.User).filter(models.User.email == "admin@sgi.ci").first()
    if not user:
        print("⚠️ Création de l'utilisateur ADMIN...")
        hashed_password = get_password_hash("admin") 
        db_user = models.User(email="admin@sgi.ci", hashed_password=hashed_password, full_name="Super Administrateur", role="ADMIN")
        db.add(db_user)
        db.commit()
        print("✅ Admin créé avec succès !")
    db.close()

# --- ROUTES GESTION DES ALERTES ---

@app.get("/alerts/", response_model=list[schemas.AlertOut])
def get_alerts(db: Session = Depends(database.get_db)):
    return db.query(models.Alert).order_by(models.Alert.created_at.desc()).all()

@app.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, update_data: schemas.AlertUpdate, db: Session = Depends(database.get_db)):
    db_alert = db.query(models.Alert).filter(models.Alert.id == alert_id).first()
    if not db_alert:
        raise HTTPException(status_code=404, detail="Alerte non trouvée")
    
    # Mise à jour dynamique des champs envoyés
    for var, value in update_data.dict(exclude_unset=True).items():
        setattr(db_alert, var, value)
    
    db.commit()
    return {"status": "success", "message": f"Alerte {alert_id} mise à jour"}


