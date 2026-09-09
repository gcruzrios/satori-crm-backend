from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.company import Company

router = APIRouter(prefix="/companies", tags=["companies"])


def _serialize_company(company: Company) -> dict:
    return {
        "id": str(company.id),
        "name": company.name,
        "legal_name": company.legal_name,
        "tax_id": company.tax_id,
        "industry": company.industry,
        "email": company.email,
        "phone": company.phone,
        "website": company.website,
        "address": company.address,
        "city": company.city,
        "country": company.country,
        "notes": company.notes,
        "created_at": company.created_at.isoformat() if company.created_at else None,
        "updated_at": company.updated_at.isoformat() if company.updated_at else None,
    }


class CompanyCreate(BaseModel):
    name: str
    legal_name: str | None = None
    tax_id: str | None = None
    industry: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    country: str | None = "Costa Rica"
    notes: str | None = None


@router.get("")
async def list_companies(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Company).where(Company.deleted_at.is_(None))
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Company.name).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {
        "items": [_serialize_company(item) for item in items],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.post("")
async def create_company(payload: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = Company(**payload.model_dump(exclude_none=True))
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return _serialize_company(company)


@router.get("/{company_id}")
async def get_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Company not found")
    return _serialize_company(company)


@router.put("/{company_id}")
async def update_company(company_id: UUID, payload: CompanyCreate, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)
    return _serialize_company(company)


@router.delete("/{company_id}")
async def delete_company(company_id: UUID, db: AsyncSession = Depends(get_db)):
    company = await db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    company.deleted_at = __import__("datetime").datetime.utcnow()
    await db.commit()
    return {"status": "deleted"}
