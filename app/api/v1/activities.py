from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.activity import Activity

router = APIRouter(prefix="/activities", tags=["activities"])


class ActivityCreate(BaseModel):
    type: str = "task"
    status: str = "pending"
    title: str
    description: str | None = None
    opportunity_id: str | None = None
    lead_id: str | None = None
    contact_id: str | None = None
    company_id: str | None = None
    assigned_to: str | None = None
    due_at: datetime | None = None


def _serialize_activity(activity: Activity) -> dict:
    return {
        "id": str(activity.id),
        "type": activity.type,
        "title": activity.title,
        "description": activity.description,
        "status": activity.status,
        "lead_id": str(activity.lead_id) if activity.lead_id else None,
        "contact_id": str(activity.contact_id) if activity.contact_id else None,
        "company_id": str(activity.company_id) if activity.company_id else None,
        "opportunity_id": str(activity.opportunity_id) if activity.opportunity_id else None,
        "assigned_to": str(activity.assigned_to) if activity.assigned_to else None,
        "due_at": activity.due_at.isoformat() if activity.due_at else None,
        "completed_at": activity.completed_at.isoformat() if activity.completed_at else None,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


@router.get("")
async def list_activities(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Activity).where(Activity.deleted_at.is_(None)).order_by(Activity.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [_serialize_activity(item) for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_activity(payload: ActivityCreate, db: AsyncSession = Depends(get_db)):
    activity = Activity(**payload.model_dump(exclude_none=True))
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return _serialize_activity(activity)


@router.get("/{activity_id}")
async def get_activity(activity_id: UUID, db: AsyncSession = Depends(get_db)):
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return _serialize_activity(activity)


@router.put("/{activity_id}")
async def update_activity(activity_id: UUID, payload: ActivityCreate, db: AsyncSession = Depends(get_db)):
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(activity, field, value)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{activity_id}")
async def delete_activity(activity_id: UUID, db: AsyncSession = Depends(get_db)):
    activity = await db.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    activity.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "deleted"}
