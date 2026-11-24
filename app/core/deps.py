from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import get_capabilities_by_role
from app.core.security import decode_access_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)

# Action endpoints (last path segment) that need their own capability. Anything not
# listed here falls back to `<resource>:write`.
_ACTION_CAPABILITY = {
    ("leads", "convert"): "leads:convert",
    ("quotes", "send"): "quotes:send",
    ("opportunities", "move"): "pipeline:move",
}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = UUID(str(payload["sub"]))
    except (ValueError, KeyError):
        raise _UNAUTHORIZED
    user = await db.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise _UNAUTHORIZED
    return user


def user_has_capability(user: User, capability: str) -> bool:
    return capability in get_capabilities_by_role(user.role)


def require_capability(capability: str):
    async def checker(user: User = Depends(get_current_user)) -> User:
        if not user_has_capability(user, capability):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


def require_access(resource: str | None):
    """Router-level guard. Requires login; if `resource` is given, also the capability
    `<resource>:read` for GET/HEAD, `<resource>:write` for other methods, or
    `<resource>:convert|send|move` for the matching action endpoints."""

    async def checker(request: Request, user: User = Depends(get_current_user)) -> User:
        if resource is None:
            return user
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            capability = f"{resource}:read"
        else:
            last = request.url.path.rstrip("/").rsplit("/", 1)[-1]
            capability = _ACTION_CAPABILITY.get((resource, last), f"{resource}:write")
        if not user_has_capability(user, capability):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker
