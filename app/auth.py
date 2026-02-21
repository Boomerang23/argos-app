# app/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# --- bcrypt hotfix (si nécessaire dans ton env) ---
import bcrypt  # noqa: F401
bcrypt.__about__ = type("type", (object,), {"__version__": bcrypt.__version__})

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from . import models, database


# -----------------------------------------------------------------------------
# Settings (ENV)
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is missing. Set it in your environment (.env).")


# -----------------------------------------------------------------------------
# Security primitives
# -----------------------------------------------------------------------------
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# IMPORTANT:
# tokenUrl doit matcher ton endpoint de login (souvent POST /token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# -----------------------------------------------------------------------------
# JWT helpers
# -----------------------------------------------------------------------------
def create_access_token(
    *,
    subject: str,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """
    subject = identifiant principal (ici email)
    extra_claims = ex: {"role": "ADMIN", "organization_id": 123}
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# -----------------------------------------------------------------------------
# Current user dependency
# -----------------------------------------------------------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise credentials_exception

    return user


# -----------------------------------------------------------------------------
# Role-based access helpers
# -----------------------------------------------------------------------------
def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    # Adapte selon ton modèle: current_user.role == "ADMIN" ou is_admin bool, etc.
    if getattr(current_user, "role", None) != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


def require_agent_or_admin(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    role = getattr(current_user, "role", None)
    if role not in {"AGENT", "ADMIN"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agent/Admin role required",
        )
    return current_user
