from fastapi.security import OAuth2PasswordRequestForm
from . import auth
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from . import models, schemas, database


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


# Exemple d'endpoint : Créer un client (Onboarding)
@app.post("/clients/", response_model=schemas.ClientOut)
def create_client(client: schemas.ClientCreate, db: Session = Depends(database.get_db), current_user: models.User = Depends(auth.get_current_user)):
    # 1. D'abord, on lance le Screening (Le Garde du Corps)
    screening_service = ScreeningService()
    # On passe 'db' à la fonction
    matches = screening_service.check_name(db, client.full_name)
        
    # 2. Si on trouve une correspondance dangereuse (Risque Élevé)
    if matches:
        # On récupère le nom du criminel trouvé
        criminel_trouve = matches[0]['matched_name']
        score = matches[0]['score']
        
        # ON BLOQUE TOUT ! On renvoie une erreur 403 (Interdit)
        raise HTTPException(
            status_code=403, 
            detail=f"ALERTE AML : Ce client ressemble à '{criminel_trouve}' (Score: {score}%). Création bloquée."
        )

    # 3. Si tout est propre, on continue l'enregistrement normal
    db_client = models.Client(**client.dict())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

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
