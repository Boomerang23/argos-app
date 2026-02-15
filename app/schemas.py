from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from .models import Role, RiskLevel, AlertStatus

# --- USER SCHEMAS ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: Role

class UserCreate(UserBase):
    password: str
    tenant_id: str # ID de la SGI

class UserOut(UserBase):
    id: UUID
    is_active: bool
    mfa_enabled: bool
    class Config:
        from_attributes = True

# --- CLIENT SCHEMAS (KYC) ---
class ClientCreate(BaseModel):
    full_name: str
    entity_type: str # 'Physique' ou 'Morale'
    national_id: str
    country_residence: str = "Côte d'Ivoire"
    tenant_id: str

class ClientOut(ClientCreate):
    id: UUID
    is_pep: bool
    risk_score: RiskLevel
    class Config:
        from_attributes = True

# --- SCREENING SCHEMAS ---
class ScreeningRequest(BaseModel):
    name: str

class ScreeningResult(BaseModel):
    input_name: str
    matches: list[dict]
    risk_level: str

# --- SANCTION SCHEMAS ---
class SanctionCreate(BaseModel):
    name: str
    list_source: str = "MANUEL"

class SanctionOut(BaseModel):
    id: str
    name: str
    list_source: str
    class Config:
        from_attributes = True

# --- USER SCHEMAS ---
class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str

    token_type: str


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
