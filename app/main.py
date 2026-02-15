from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from . import models, schemas, database, auth
from .database import SessionLocal, engine


# Création automatique des tables (pour le dev, à remplacer par Alembic en prod)
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

# --- ROUTE INSCRIPTION ---
@app.post("/register", response_model=schemas.UserOut)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    # Vérifie si l'email existe déjà
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    
    # Hachage du mot de passe et sauvegarde
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

# --- ROUTE CONNEXION (Pour obtenir le jeton) ---
@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(database.get_db)):
    # Vérification des identifiants
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Génération du token
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# Exemple d'endpoint : Créer ou vérifier un client (Onboarding & Revue Périodique)
@app.post("/clients/")
def create_or_verify_client(client: schemas.ClientCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    
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
        
   # 3. La Réponse Personnalisée
    if matches:
        criminel_trouve = matches[0]['matched_name']
        liste_origine = "Liste de Surveillance" # Valeur de secours
        
        # On essaie de récupérer le profil complet
        profil = db.query(models.Sanction).filter(models.Sanction.name == criminel_trouve).first()
        
        # ON UTILISE list_source !
        if profil and hasattr(profil, 'list_source') and profil.list_source:
            liste_origine = profil.list_source
        
        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "ELEVE",
            "details": f"Correspondance parfaite avec '{criminel_trouve}' de la liste '{liste_origine}'"
        }
    else:
        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "FAIBLE",
            "details": "RAS"
        }
@app.post("/sanctions/", response_model=schemas.SanctionOut)
def add_sanction(sanction: schemas.SanctionCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_sanction = models.Sanction(**sanction.dict())
    db.add(db_sanction)
    db.commit()
    db.refresh(db_sanction)
    return db_sanction

from .services import ScreeningService

@app.post("/screening/check", response_model=schemas.ScreeningResult)
def screen_name(request: schemas.ScreeningRequest, db: Session = Depends(database.get_db)): # <-- Ajout de db
    service = ScreeningService()
    # On passe 'db' ici aussi
    matches = service.check_name(db, request.name)
    
    risk = "FAIBLE"
    if matches:
        risk = "ELEVE"
        
    return {
        "input_name": request.name,
        "matches": matches,
        "risk_level": risk

    }

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
    db_lst = db.query(models.CustomList).filter(models.CustomList.name == list_name).first()
    if db_lst:
        db.delete(db_lst)
        db.commit()
        return {"status": "deleted"}
    return {"status": "not found"}

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
        hashed_password = auth.get_password_hash("admin")
        db_user = models.User(email="admin@sgi.ci", hashed_password=hashed_password)
        db.add(db_user)
        db.commit()
        print("✅ Admin créé avec succès !")
    db.close()






