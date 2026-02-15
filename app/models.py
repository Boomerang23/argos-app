from sqlalchemy import Column, Integer, String, DateTime, Boolean
from .database import Base
import uuid
from datetime import datetime
import enum

# --- ENUMS ---
class Role(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"

class RiskLevel(str, enum.Enum):
    LOW = "FAIBLE"
    HIGH = "ELEVE"

class AlertStatus(str, enum.Enum):
    NEW = "NOUVEAU"
    CLOSED = "FERME"

# --- MODELES BDD ---

# 1. Table des CLIENTS (Mise à jour V2)
class Client(Base):
    __tablename__ = "clients_v2"  # <--- CHANGEMENT DE NOM pour recréer la table

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, index=True)
    entity_type = Column(String)
    national_id = Column(String, unique=True, index=True)
    country_residence = Column(String)
    tenant_id = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # --- NOUVEAUX CHAMPS (Pour corriger l'erreur 500) ---
    risk_score = Column(String, default="FAIBLE")
    is_pep = Column(Boolean, default=False)

# 2. Table des SANCTIONS
class Sanction(Base):
    __tablename__ = "sanctions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    list_source = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)
    

# 3. Table des UTILISATEURS
class User(Base):
    __tablename__ = "users_v2"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)

    hashed_password = Column(String)

