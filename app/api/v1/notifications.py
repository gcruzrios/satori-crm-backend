from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.notification import Notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationCreate(BaseModel):
    user_id: str
    type: str
    title: str
    body: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None


@router.get("")
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Notification).offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return {"items": [{"id": str(item.id), "title": item.title, "type": item.type} for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_notification(payload: NotificationCreate, db: AsyncSession = Depends(get_db)):
    notification = Notification(**payload.model_dump(exclude_none=True))
    db.add(notification)
    await db.commit()
    await db.refresh(notification)
    return {"id": str(notification.id), "status": "created"}


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: UUID, db: AsyncSession = Depends(get_db)):
    notification = await db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    notification.read_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    return {"status": "read"}
