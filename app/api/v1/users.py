from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


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
    total = await db.scalar(select(User).count())
    result = await db.execute(select(User).offset(offset).limit(page_size))
    items = result.scalars().all()
    return {"items": [
        {"id": str(u.id), "first_name": u.first_name, "last_name": u.last_name, "email": u.email, "role": u.role, "is_active": u.is_active}
        for u in items
    ], "total": total or 0, "page": page, "page_size": page_size}


@router.post("")
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == str(payload.email)))
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    user = User(
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=str(payload.email),
        password_hash="hashed_placeholder",
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.get("/{user_id}")
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.get(User, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": str(result.id), "first_name": result.first_name, "last_name": result.last_name, "email": result.email, "role": result.role, "is_active": result.is_active}


@router.put("/{user_id}")
async def update_user(user_id: UUID, payload: UserUpdate, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    return {"status": "updated"}


@router.post("/{user_id}/deactivate")
async def deactivate_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.commit()
    return {"status": "deactivated"}
