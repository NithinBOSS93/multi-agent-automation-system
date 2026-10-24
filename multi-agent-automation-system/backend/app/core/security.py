"""Password hashing (bcrypt) and JWT tokens."""
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "username": username, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> dict | None:
    """Returns the user payload if a valid token is sent, otherwise None (guest)."""
    if not creds:
        return None
    return decode_token(creds.credentials)


async def require_user(user: dict | None = Depends(optional_user)) -> dict:
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user
