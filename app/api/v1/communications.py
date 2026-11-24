from __future__ import annotations

from typing import Literal
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
    channel: Literal["email", "whatsapp", "phone", "web"] = "email"
    direction: Literal["inbound", "outbound"] = "outbound"
    status: Literal["queued", "sent", "delivered", "read", "failed"] = "sent"
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    company_id: UUID | None = None
    external_id: str | None = None
    from_address: str | None = None
    to_address: str | None = None
    subject: str | None = None
    message: str | None = None
    is_template: bool = False


def _serialize_communication(item: Communication) -> dict:
    return {
        "id": str(item.id),
        "channel": item.channel,
        "direction": item.direction,
        "status": item.status,
        "lead_id": str(item.lead_id) if item.lead_id else None,
        "contact_id": str(item.contact_id) if item.contact_id else None,
        "company_id": str(item.company_id) if item.company_id else None,
        "external_id": item.external_id,
        "from_address": item.from_address,
        "to_address": item.to_address,
        "subject": item.subject,
        "message": item.message,
        "is_template": item.is_template,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
async def list_communications(
    channel: Literal["email", "whatsapp", "phone", "web"] | None = None,
    lead_id: UUID | None = None,
    contact_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Communication).order_by(Communication.created_at.desc())
    if channel:
        stmt = stmt.where(Communication.channel == channel)
    if lead_id:
        stmt = stmt.where(Communication.lead_id == lead_id)
    if contact_id:
        stmt = stmt.where(Communication.contact_id == contact_id)
    items, total = await paginate(db, stmt, page, page_size)
    return {"items": [_serialize_communication(i) for i in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_communication(payload: CommunicationCreate, db: AsyncSession = Depends(get_db)):
    communication = Communication(**payload.model_dump())
    db.add(communication)
    await db.commit()
    await db.refresh(communication)
    return _serialize_communication(communication)


@router.get("/{communication_id}")
async def get_communication(communication_id: UUID, db: AsyncSession = Depends(get_db)):
    communication = await get_active_or_404(db, Communication, communication_id, "Communication")
    return _serialize_communication(communication)
