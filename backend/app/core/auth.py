import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models import User, Role, UserRole

JWT_SECRET = os.environ.get("JWT_SECRET", "clarifibids_development_secret_key_2026")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

security_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    # Use sha256 with salt for native Windows zero-dependency reliability
    salt = "clarifibids_salt_"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hash_password(plain_password) == hashed_password

def create_access_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None

async def get_current_user_optional(
    cred: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)
) -> Optional[Dict[str, Any]]:
    if not cred or not cred.credentials:
        return None
    payload = decode_access_token(cred.credentials)
    return payload
