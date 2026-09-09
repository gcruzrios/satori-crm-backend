from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.quote import Quote, QuoteItem

router = APIRouter(prefix="/quotes", tags=["quotes"])


class QuoteCreate(BaseModel):
    opportunity_id: str | None = None
    contact_id: str | None = None
    company_id: str | None = None
    status: str = "draft"
    subtotal: float = 0
    discount: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "CRC"
    valid_until: date | None = None
    notes: str | None = None


def _serialize_quote(quote: Quote) -> dict:
    return {
        "id": str(quote.id),
        "quote_number": quote.quote_number,
        "opportunity_id": str(quote.opportunity_id) if quote.opportunity_id else None,
        "contact_id": str(quote.contact_id) if quote.contact_id else None,
        "company_id": str(quote.company_id) if quote.company_id else None,
        "status": quote.status,
        "subtotal": str(quote.subtotal),
        "discount": str(quote.discount),
        "tax": str(quote.tax),
        "total": str(quote.total),
        "currency": quote.currency,
        "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
        "notes": quote.notes,
        "created_at": quote.created_at.isoformat() if quote.created_at else None,
        "updated_at": quote.updated_at.isoformat() if quote.updated_at else None,
        "sent_at": quote.sent_at.isoformat() if quote.sent_at else None,
        "accepted_at": quote.accepted_at.isoformat() if quote.accepted_at else None,
    }


@router.get("")
async def list_quotes(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Quote).where(Quote.deleted_at.is_(None)).order_by(Quote.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [_serialize_quote(item) for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_quote(payload: QuoteCreate, db: AsyncSession = Depends(get_db)):
    if not payload.contact_id and not payload.company_id:
        raise HTTPException(status_code=400, detail="La cotización requiere contact_id o company_id")

    quote_number = await db.scalar(text("SELECT next_document_number('quote', 'COT')"))
    quote = Quote(quote_number=quote_number, **payload.model_dump(exclude={"valid_until"}, exclude_none=True))
    quote.valid_until = payload.valid_until
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return _serialize_quote(quote)


@router.get("/{quote_id}")
async def get_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return _serialize_quote(quote)


@router.put("/{quote_id}")
async def update_quote(quote_id: UUID, payload: QuoteCreate, db: AsyncSession = Depends(get_db)):
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(quote, field, value)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{quote_id}")
async def delete_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{quote_id}/send")
async def send_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote.status = "sent"
    quote.sent_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "sent", "quote_id": str(quote.id)}


@router.post("/{quote_id}/accept")
async def accept_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await db.get(Quote, quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    quote.status = "accepted"
    quote.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "accepted", "quote_id": str(quote.id)}
