from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead

router = APIRouter(prefix="/leads", tags=["leads"])


def _serialize_lead(lead: Lead) -> dict:
    return {
        "id": str(lead.id),
        "lead_type": lead.lead_type,
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "company_name": lead.company_name,
        "email": lead.email,
        "phone": lead.phone,
        "whatsapp": lead.whatsapp,
        "source": lead.source,
        "source_reference": lead.source_reference,
        "status": lead.status,
        "score": lead.score,
        "message": lead.message,
        "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
        "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
    }


class LeadCreate(BaseModel):
    lead_type: str = "individual"
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    whatsapp: str | None = None
    source: str = "website"
    source_reference: str | None = None
    status: str = "new"
    score: int = 0
    message: str | None = None
    assigned_to: str | None = None


class LeadUpdate(LeadCreate):
    pass


@router.get("")
async def list_leads(
    status: str | None = None,
    source: str | None = None,
    lead_type: str | None = None,
    assigned_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lead).where(Lead.deleted_at.is_(None))
    if status:
        stmt = stmt.where(Lead.status == status)
    if source:
        stmt = stmt.where(Lead.source == source)
    if lead_type:
        stmt = stmt.where(Lead.lead_type == lead_type)
    if assigned_to:
        stmt = stmt.where(Lead.assigned_to == assigned_to)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Lead.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [_serialize_lead(item) for item in items], "total": total or 0, "page": page, "page_size": page_size}


@router.post("")
async def create_lead(payload: LeadCreate, db: AsyncSession = Depends(get_db)):
    lead = Lead(**payload.model_dump(exclude_none=True))
    db.add(lead)
    await db.commit()
    await db.refresh(lead)
    return _serialize_lead(lead)


@router.get("/{lead_id}")
async def get_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead or lead.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Lead not found")
    return _serialize_lead(lead)


@router.put("/{lead_id}")
async def update_lead(lead_id: UUID, payload: LeadUpdate, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return _serialize_lead(lead)


@router.delete("/{lead_id}")
async def delete_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    lead.deleted_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    return {"status": "deleted"}


@router.post("/{lead_id}/convert")
async def convert_lead(lead_id: UUID, db: AsyncSession = Depends(get_db)):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "converted", "lead_id": str(lead.id)}
