from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def _encode(subject: str, token_type: str, expires: timedelta) -> str:
    to_encode: dict[str, Any] = {"sub": subject, "type": token_type, "exp": datetime.now(timezone.utc) + expires}
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def _decode(token: str, token_type: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc
    if payload.get("type") != token_type:
        raise ValueError("wrong token type")
    return payload


def create_access_token(subject: str, expires_delta: int | None = None) -> str:
    return _encode(subject, "access", timedelta(minutes=expires_delta or settings.access_token_expire_minutes))


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode(token, "access")


def create_refresh_token(subject: str) -> str:
    return _encode(subject, "refresh", timedelta(days=settings.refresh_token_expire_days))


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode(token, "refresh")
