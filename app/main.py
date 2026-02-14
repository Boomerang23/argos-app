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
    
    # 1. On vérifie si le client existe DÉJÀ dans la base (avec sa pièce d'identité)
    db_client = db.query(models.Client).filter(models.Client.national_id == client.national_id).first()
    
    if db_client:
        # S'il existe, on met à jour son nom (au cas où il y a eu un changement de nom martial, etc.)
        db_client.full_name = client.full_name
    else:
        # S'il n'existe pas, on l'ajoute
        db_client = models.Client(**client.dict())
        db.add(db_client)
        
    # On sauvegarde (plus d'erreur de doublon car on a géré le cas au-dessus)
    db.commit()
    db.refresh(db_client)

    # 2. On lance le Screening (Le Garde du Corps)
    from .services import ScreeningService
    screening_service = ScreeningService()
    matches = screening_service.check_name(db, client.full_name)
        
    # 3. On renvoie le résultat formaté pour le Frontend
    if matches:
        criminel_trouve = matches[0]['matched_name']
        score = matches[0]['score']
        # Au lieu de crasher (403), on renvoie un statut ELEVE que Streamlit comprendra
        return {
            "id": db_client.id,
            "full_name": db_client.full_name,
            "national_id": db_client.national_id,
            "risk_score": "ELEVE",
            "details": f"Sanction/PEP: {criminel_trouve}"
        }
    else:
        # Le client est propre
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


