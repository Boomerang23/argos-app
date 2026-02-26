# app/auth.py
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

# Hotfix bcrypt (si ton env en a besoin)
import bcrypt  # noqa: F401
bcrypt.__about__ = type("type", (object,), {"__version__": bcrypt.__version__})

from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models, database


# ----------------------------
# Config JWT / Cookies
# ----------------------------
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

# Refresh token (cookie httpOnly)
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "14"))
REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "argos_refresh")

# Cookies
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"   # True en prod HTTPS
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")                  # dev=lax, prod cross-site=none
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")                             # ex: ".argos360.com" (optionnel)

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY missing. Set it in environment (.env locally or host vars).")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Important: on pointe vers le login SaaS
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ----------------------------
# Password helpers
# ----------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# ----------------------------
# JWT helpers
# ----------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(
    subject: str,
    expires_minutes: Optional[int] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """
    subject recommandé = user_id (str)
    """
    exp = _now_utc() + timedelta(minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": subject,
        "type": "access",
        "iat": _now_utc(),
        "exp": exp,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    subject: str,
    extra_claims: Optional[dict] = None,
) -> str:
    """
    subject recommandé = user_id (str)
    """
    exp = _now_utc() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "type": "refresh",
        "iat": _now_utc(),
        "exp": exp,
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def decode_refresh_token(token: str) -> dict:
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return payload


# ----------------------------
# Current user dependency
# ----------------------------
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(database.get_db),
) -> models.User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise cred_exc
    except JWTError:
        raise cred_exc

    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user:
        raise cred_exc

    return user

# ----------------------------
# RBAC helpers
# ----------------------------
def require_super_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Super admin required")
    return current_user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user


def require_agent_or_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role not in {"SUPER_ADMIN", "ADMIN", "AGENT"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
    return current_user