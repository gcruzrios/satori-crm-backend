from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import get_active_or_404
from app.core.permissions import ROLE_CAPABILITIES
from app.core.security import hash_password
from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


def _validate_role(role: str) -> None:
    if role not in ROLE_CAPABILITIES:
        raise HTTPException(status_code=422, detail=f"Invalid role. Allowed: {', '.join(ROLE_CAPABILITIES)}")


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    role: str = "sales"



class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    role: str | None = None
    is_active: bool | None = None


@router.get("")
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    offset = (page - 1) * page_size
    base = select(User).where(User.deleted_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(base.subquery()))
    result = await db.execute(base.order_by(User.created_at.desc()).offset(offset).limit(page_size))
    items = result.scalars().all()
    return {"items": [
        {"id": str(u.id), "first_name": u.first_name, "last_name": u.last_name, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in items
    ], "total": total or 0, "page": page, "page_size": page_size}


@router.post("")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    _validate_role(payload.role)
    email = str(payload.email).lower()
    existing = await db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.get("/{user_id}")
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await get_active_or_404(db, User, user_id, "User")
    return {"id": str(result.id), "first_name": result.first_name, "last_name": result.last_name, "email": result.email, "role": result.role, "is_active": result.is_active}


@router.put("/{user_id}")
async def update_user(user_id: UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await get_active_or_404(db, User, user_id, "User")
    data = payload.model_dump(exclude_unset=True)
    if data.get("role") is not None:
        _validate_role(data["role"])
    if data.get("email") is not None:
        data["email"] = str(data["email"]).lower()
        taken = await db.scalar(select(User).where(User.email == data["email"], User.id != user.id))
        if taken:
            raise HTTPException(status_code=400, detail="Email already exists")
    for field, value in data.items():
        if value is not None:  # none of these columns are nullable
            setattr(user, field, value)
    await db.commit()
    return {"status": "updated"}


@router.post("/{user_id}/deactivate")
async def deactivate_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await get_active_or_404(db, User, user_id, "User")
    user.is_active = False
    await db.commit()
    return {"status": "deactivated"}
