from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import paginate, apply_updates, get_active_or_404, partial_model, utcnow
from app.core.database import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.opportunity import Opportunity
from app.models.pipeline import PipelineStage

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


class OpportunityCreate(BaseModel):
    name: str
    pipeline_id: UUID
    stage_id: UUID
    lead_id: UUID | None = None
    contact_id: UUID | None = None
    company_id: UUID | None = None
    expected_value: float | None = None
    currency: str = "CRC"
    probability: int | None = None
    expected_close_date: date | None = None
    status: str = "open"
    assigned_to: UUID | None = None
    notes: str | None = None



OpportunityUpdate = partial_model(OpportunityCreate, "OpportunityUpdate")


class OpportunityMove(BaseModel):
    stage_id: UUID

def serialize_opportunity(o: Opportunity, names: dict | None = None) -> dict:
    names = names or {}
    def iso(v):
        return v.isoformat() if v is not None else None

    def uid(v):
        return str(v) if v is not None else None

    return {
        "id": str(o.id),
        "name": o.name,
        "pipeline_id": uid(o.pipeline_id),
        "stage_id": uid(o.stage_id),
        "lead_id": uid(o.lead_id),
        "contact_id": uid(o.contact_id),
        "company_id": uid(o.company_id),
        "expected_value": float(o.expected_value) if o.expected_value is not None else None,
        "currency": o.currency,
        "probability": o.probability,
        "expected_close_date": iso(o.expected_close_date),
        "status": o.status,
        "assigned_to": uid(o.assigned_to),
        "notes": o.notes,
        "created_at": iso(o.created_at),
        "updated_at": iso(o.updated_at),
        "closed_at": iso(o.closed_at),
        "contact_name": names.get(("contact", o.contact_id)),
        "company_name": names.get(("company", o.company_id)),
        "stage_name": names.get(("stage", o.stage_id)),
    }


async def _display_names(db: AsyncSession, items: list[Opportunity]) -> dict:
    """Lookup contact/company/stage names for a batch of opportunities (one query each)."""
    names: dict = {}
    contact_ids = {o.contact_id for o in items if o.contact_id}
    company_ids = {o.company_id for o in items if o.company_id}
    stage_ids = {o.stage_id for o in items if o.stage_id}
    if contact_ids:
        rows = await db.execute(select(Contact.id, Contact.first_name, Contact.last_name).where(Contact.id.in_(contact_ids)))
        names.update({("contact", cid): f"{first} {last}".strip() for cid, first, last in rows.all()})
    if company_ids:
        rows = await db.execute(select(Company.id, Company.name).where(Company.id.in_(company_ids)))
        names.update({("company", cid): name for cid, name in rows.all()})
    if stage_ids:
        rows = await db.execute(select(PipelineStage.id, PipelineStage.name).where(PipelineStage.id.in_(stage_ids)))
        names.update({("stage", sid): name for sid, name in rows.all()})
    return names


@router.get("")
async def list_opportunities(
    pipeline_id: UUID | None = None,
    stage_id: UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Opportunity).where(Opportunity.deleted_at.is_(None)).order_by(Opportunity.created_at.desc())
    if pipeline_id:
        stmt = stmt.where(Opportunity.pipeline_id == pipeline_id)
    if stage_id:
        stmt = stmt.where(Opportunity.stage_id == stage_id)
    if status:
        stmt = stmt.where(Opportunity.status == status)
    items, total = await paginate(db, stmt, page, page_size)
    names = await _display_names(db, items)
    return {"items": [serialize_opportunity(item, names) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_opportunity(payload: OpportunityCreate, db: AsyncSession = Depends(get_db)):
    opportunity = Opportunity(**payload.model_dump(exclude_none=True))
    db.add(opportunity)
    await db.commit()
    await db.refresh(opportunity)
    return {"id": str(opportunity.id), "status": "created"}


@router.get("/{opportunity_id}")
async def get_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opportunity = await get_active_or_404(db, Opportunity, opportunity_id, "Opportunity")
    return serialize_opportunity(opportunity, await _display_names(db, [opportunity]))


@router.put("/{opportunity_id}")
async def update_opportunity(opportunity_id: UUID, payload: OpportunityUpdate, db: AsyncSession = Depends(get_db)):
    opportunity = await get_active_or_404(db, Opportunity, opportunity_id, "Opportunity")
    apply_updates(opportunity, payload)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{opportunity_id}")
async def delete_opportunity(opportunity_id: UUID, db: AsyncSession = Depends(get_db)):
    opportunity = await get_active_or_404(db, Opportunity, opportunity_id, "Opportunity")
    opportunity.deleted_at = utcnow()
    await db.commit()
    return {"status": "deleted"}


@router.post("/{opportunity_id}/move")
async def move_opportunity(opportunity_id: UUID, payload: OpportunityMove, db: AsyncSession = Depends(get_db)):
    """Move an opportunity to another stage of its pipeline (won/lost stages close it)."""
    opportunity = await get_active_or_404(db, Opportunity, opportunity_id, "Opportunity")
    stage = await db.get(PipelineStage, payload.stage_id)
    if stage is None or stage.pipeline_id != opportunity.pipeline_id:
        raise HTTPException(status_code=422, detail="Stage does not belong to the opportunity's pipeline")
    opportunity.stage_id = stage.id
    opportunity.probability = stage.probability
    if stage.is_won:
        opportunity.status, opportunity.closed_at = "won", utcnow()
    elif stage.is_lost:
        opportunity.status, opportunity.closed_at = "lost", utcnow()
    else:
        opportunity.status, opportunity.closed_at = "open", None
    await db.commit()
    return {"status": "moved", "opportunity_id": str(opportunity.id), "stage_id": str(stage.id), "opportunity_status": opportunity.status}
