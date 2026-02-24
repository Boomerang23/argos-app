from sqlalchemy import Column, Integer, String, DateTime, Boolean, Float, ForeignKey
from .database import Base
import uuid
from datetime import datetime


# --- 0) ORGANIZATIONS (TENANTS) ---
class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# --- 1) CLIENTS ---
class Client(Base):
    __tablename__ = "clients_v2"  # on garde tel quel pour ne pas casser ta table existante

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    full_name = Column(String, index=True)
    entity_type = Column(String)
    national_id = Column(String, unique=True, index=True)
    country_residence = Column(String)

    # legacy: à terme tu peux le supprimer, mais on le garde pour compat
    tenant_id = Column(String, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    risk_score = Column(String, default="FAIBLE")
    is_pep = Column(Boolean, default=False)


# --- 2) SANCTIONS ---
class Sanction(Base):
    __tablename__ = "sanctions"

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    name = Column(String, index=True)
    list_source = Column(String)
    added_at = Column(DateTime, default=datetime.utcnow)


# --- 3) UTILISATEURS (UNIQUE) ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    full_name = Column(String)
    role = Column(String, default="AGENT")  # "ADMIN" ou "AGENT"
    is_active = Column(Boolean, default=True)


# --- 4) AUDIT LOGS ---
class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    timestamp = Column(String)
    user_email = Column(String)
    action = Column(String)
    target = Column(String)
    details = Column(String)


# --- 5) HISTORIQUE DES SCANS ---
class ScanHistory(Base):
    __tablename__ = "scan_history"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    date = Column(String)
    client_name = Column(String)
    status = Column(String)
    details = Column(String)

# --- 6) LISTES CUSTOM ---
class CustomList(Base):
    __tablename__ = "custom_lists"

    name = Column(String, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)


# --- 7) ALERTES (CASE MANAGEMENT) ---
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), index=True, nullable=True)

    client_name = Column(String)
    matched_name = Column(String)
    similarity_score = Column(Float)

    status = Column(String, default="OUVERT")  # OUVERT, EN_COURS, FERME
    decision = Column(String, nullable=True)   # FAUX_POSITIF / CONFIRME
    comments = Column(String, nullable=True)

    assigned_to = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)