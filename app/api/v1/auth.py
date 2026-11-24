from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.permissions import get_capabilities_by_role
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, verify_password
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# The refresh cookie is only ever sent to the auth endpoints.
_COOKIE_PATH = "/api/v1/auth"


def _set_refresh_cookie(response: Response, user_id: str) -> None:
    # Cross-site frontends (crm.satori.cr -> API host) need SameSite=None + Secure.
    # In development (same-origin Vite proxy over http) use Lax and no Secure flag.
    dev = settings.app_env == "development"
    response.set_cookie(
        settings.refresh_cookie_name,
        create_refresh_token(user_id),
        max_age=settings.refresh_token_expire_days * 86400,
        httponly=True,
        secure=not dev,
        samesite="lax" if dev else "none",
        path=_COOKIE_PATH,
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: dict[str, str]


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == payload.email.lower()))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active or user.deleted_at is not None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(subject=str(user.id))
    _set_refresh_cookie(response, str(user.id))
    return TokenResponse(
        access_token=token,
        user={"email": user.email, "role": user.role, "first_name": user.first_name, "last_name": user.last_name},
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "capabilities": get_capabilities_by_role(user.role),
    }


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Exchange the httpOnly refresh cookie for a new access token (and rotate the cookie)."""
    invalid = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if not refresh_token:
        raise invalid
    try:
        user_id = UUID(str(decode_refresh_token(refresh_token)["sub"]))
    except (ValueError, KeyError):
        raise invalid
    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise invalid
    _set_refresh_cookie(response, str(user.id))
    return {"access_token": create_access_token(subject=str(user.id)), "token_type": "bearer"}


@router.post("/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(settings.refresh_cookie_name, path=_COOKIE_PATH)
    return {"status": "logged_out"}
