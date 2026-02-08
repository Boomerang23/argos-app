from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Récupération de l'URL de la base de données (Sécurité : jamais en dur dans le code)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Création du moteur de base de données
# pool_pre_ping=True est vital pour éviter les déconnexions silencieuses
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dépendance pour récupérer la session DB dans chaque requête API
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()