from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import get_active_or_404, paginate
from app.core.database import get_db
from app.models.communication import Communication

router = APIRouter(prefix="/communications", tags=["communications"])


class CommunicationCreate(BaseModel):
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    opportunity_id: UUID | None = None
    channel: str = "email"
    direction: str = "outbound"
    status: str = "queued"
    subject: str | None = None
    body: str | None = None


@router.get("")
async def list_communications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Communication).order_by(Communication.created_at.desc())
    items, total = await paginate(db, stmt, page, page_size)
    return {"items": [{"id": str(item.id), "channel": item.channel, "status": item.status} for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_communication(payload: CommunicationCreate, db: AsyncSession = Depends(get_db)):
    communication = Communication(**payload.model_dump(exclude_none=True))
    db.add(communication)
    await db.commit()
    await db.refresh(communication)
    return {"id": str(communication.id), "status": "created"}


@router.get("/{communication_id}")
async def get_communication(communication_id: UUID, db: AsyncSession = Depends(get_db)):
    communication = await get_active_or_404(db, Communication, communication_id, "Communication")
    return {"id": str(communication.id), "channel": communication.channel, "status": communication.status}
