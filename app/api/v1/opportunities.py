from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.opportunity import Opportunity

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


class OpportunityCreate(BaseModel):
    name: str
    pipeline_id: str
    stage_id: str
    lead_id: str | None = None
    contact_id: str | None = None
    company_id: str | None = None
    expected_value: float | None = None
    currency: str = "CRC"
    probability: int | None = None
    expected_close_date: str | None = None
    status: str = "open"
    assigned_to: str | None = None
    notes: str | None = None


@router.get("")
async def list_opportunities(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Opportunity).offset((page - 1) * page_size).limit(page_size))
    items = result.scalars().all()
    return {"items": [{"id": str(item.id), "name": item.name, "status": item.status} for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_opportunity(payload: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    opportunity = Opportunity(**payload.model_dump(exclude_none=True))
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)
    return {"id": str(opportunity.id), "status": "created"}


@router.get("/{opportunity_id}")
async def get_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"id": str(opportunity.id), "name": opportunity.name, "status": opportunity.status}


@router.put("/{opportunity_id}")
async def update_opportunity(opportunity_id: UUID, payload: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(opportunity, field, value)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{opportunity_id}")
async def delete_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opportunity.deleted_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    return {"status": "deleted"}


@router.post("/{opportunity_id}/move")
async def move_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opportunity = await db.get(Opportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"status": "moved", "opportunity_id": str(opportunity.id)}
