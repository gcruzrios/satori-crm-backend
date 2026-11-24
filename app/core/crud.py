from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, TypeVar
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, create_model
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def get_active_or_404(db: AsyncSession, model: type[T], object_id: UUID, label: str) -> T:
    """Fetch a row by id; soft-deleted rows are treated as missing."""
    obj = await db.get(model, object_id)
    if obj is None or getattr(obj, "deleted_at", None) is not None:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return obj


def apply_updates(obj: Any, payload: BaseModel) -> None:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)


def partial_model(model: type[BaseModel], name: str) -> type[BaseModel]:
    """Build an update schema from a create schema: every field optional (default None)."""
    fields = {
        fname: (finfo.annotation | None, None)  # type: ignore[operator]
        for fname, finfo in model.model_fields.items()
    }
    return create_model(name, **fields)  # type: ignore[call-overload]


async def paginate(db: AsyncSession, stmt: Any, page: int, page_size: int) -> tuple[list[Any], int]:
    """Run `stmt` with offset/limit and also return the total row count."""
    total = await db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    return list(result.scalars().all()), total or 0
