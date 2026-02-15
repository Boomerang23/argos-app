from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

# --- AUTH & JETONS ---
class Token(BaseModel):
    access_token: str
    token_type: str

# --- USER SCHEMAS (Gestion des accès) ---
class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "AGENT"

class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

# --- CLIENT SCHEMAS (KYC) ---
class ClientCreate(BaseModel):
    full_name: str
    entity_type: str = "Physique" # 'Physique' ou 'Morale'
    national_id: str
    country_residence: str = "Côte d'Ivoire"
    tenant_id: Optional[str] = "MANUAL"

class ClientOut(ClientCreate):
    id: int
    risk_score: str
    class Config:
        from_attributes = True

# --- SCREENING SCHEMAS (IA & Recherche floue) ---
class ScreeningRequest(BaseModel):
    name: str

class ScreeningResult(BaseModel):
    input_name: str
    matches: List[dict]
    risk_level: str

# --- SANCTION SCHEMAS (Listes Noires) ---
class SanctionCreate(BaseModel):
    name: str
    list_source: str = "MANUAL"

class SanctionOut(BaseModel):
    id: int
    name: str
    list_source: str
    class Config:
        from_attributes = True

# --- ALERT SCHEMAS (Gestion des dossiers/Tickets) ---
class AlertOut(BaseModel):
    id: int
    client_name: str
    matched_name: str
    similarity_score: float
    status: str
    decision: Optional[str]
    comments: Optional[str]
    assigned_to: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class AlertUpdate(BaseModel):
    status: Optional[str]
    decision: Optional[str]
    comments: Optional[str]
    assigned_to: Optional[str]

# --- LOGS & AUDIT SCHEMAS ---
class AuditLogCreate(BaseModel):
    timestamp: str
    user_email: str
    action: str
    target: str
    details: str

class ScanHistoryCreate(BaseModel):
    date: str
    client_name: str
    status: str
    details: str

class CustomListCreate(BaseModel):
    name: str
