from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.company import Company
from app.models.contact import Contact

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _serialize_contact(contact: Contact, company_name: str | None = None) -> dict:
    return {
        "id": str(contact.id),
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "email": contact.email,
        "phone": contact.phone,
        "whatsapp": contact.whatsapp,
        "job_title": contact.job_title,
        "company_id": str(contact.company_id) if contact.company_id else None,
        "company_name": company_name,
        "lead_id": str(contact.lead_id) if contact.lead_id else None,
        "notes": contact.notes,
        "created_at": contact.created_at.isoformat() if contact.created_at else None,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


async def _company_names(db: AsyncSession, contacts: list[Contact]) -> dict[str, str]:
    ids = {c.company_id for c in contacts if c.company_id}
    if not ids:
        return {}
    rows = await db.execute(select(Company.id, Company.name).where(Company.id.in_(ids)))
    return {str(cid): name for cid, name in rows.all()}


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    job_title: str | None = None
    company_id: str | None = None
    lead_id: str | None = None
    notes: str | None = None


@router.get("")
async def list_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Contact).where(Contact.deleted_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Contact.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    names = await _company_names(db, items)
    return {
        "items": [
            _serialize_contact(item, names.get(str(item.company_id))) for item in items
        ],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_contact(payload: ContactCreate, db: AsyncSession = Depends(get_db)):
    contact = Contact(**payload.model_dump(exclude_none=True))
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    names = await _company_names(db, [contact])
    return _serialize_contact(contact, names.get(str(contact.company_id)))


@router.get("/{contact_id}")
async def get_contact(contact_id: UUID, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if not contact or contact.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Contact not found")
    names = await _company_names(db, [contact])
    return _serialize_contact(contact, names.get(str(contact.company_id)))


@router.put("/{contact_id}")
async def update_contact(contact_id: UUID, payload: ContactCreate, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    await db.commit()
    await db.refresh(contact)
    names = await _company_names(db, [contact])
    return _serialize_contact(contact, names.get(str(contact.company_id)))


@router.delete("/{contact_id}")
async def delete_contact(contact_id: UUID, db: AsyncSession = Depends(get_db)):
    contact = await db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    contact.deleted_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    return {"status": "deleted"}
