from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.communication import Communication

router = APIRouter(prefix="/communications", tags=["communications"])


class CommunicationCreate(BaseModel):
    lead_id: str | None = None
    contact_id: str | None = None
    opportunity_id: str | None = None
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
    result = await db.execute(select(Communication).offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return {"items": [{"id": str(item.id), "channel": item.channel, "status": item.status} for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_communication(payload: CommunicationCreate, db: AsyncSession = Depends(get_db)):
    communication = Communication(**payload.model_dump(exclude_none=True))
    db.add(communication)
    await db.commit()
    await db.refresh(communication)
    return {"id": str(communication.id), "status": "created"}


@router.get("/{communication_id}")
async def get_communication(communication_id: UUID, db: AsyncSession = Depends(get_db)):
    communication = await db.get(Communication, communication_id)
    if not communication:
        raise HTTPException(status_code=404, detail="Communication not found")
    return {"id": str(communication.id), "channel": communication.channel, "status": communication.status}
