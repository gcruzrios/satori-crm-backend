from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import paginate, apply_updates, get_active_or_404, partial_model, utcnow
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.quote import Quote
from app.models.user import User

router = APIRouter(prefix="/quotes", tags=["quotes"])


class QuoteCreate(BaseModel):
    opportunity_id: UUID | None = None
    contact_id: UUID | None = None
    company_id: UUID | None = None
    status: str = "draft"
    subtotal: float = 0
    discount: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "CRC"
    valid_until: date | None = None
    notes: str | None = None



QuoteUpdate = partial_model(QuoteCreate, "QuoteUpdate")

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
    items, total = await paginate(db, stmt, page, page_size)
    return {"items": [_serialize_quote(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_quote(payload: QuoteCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.contact_id and not payload.company_id:
        raise HTTPException(status_code=400, detail="La cotización requiere contact_id o company_id")

    quote_number = await db.scalar(text("SELECT next_document_number('quote', 'COT')"))
    quote = Quote(quote_number=quote_number, created_by=user.id, **payload.model_dump(exclude={"valid_until"}, exclude_none=True))
    quote.valid_until = payload.valid_until
    db.add(quote)
    await db.commit()
    await db.refresh(quote)
    return _serialize_quote(quote)


@router.get("/{quote_id}")
async def get_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await get_active_or_404(db, Quote, quote_id, "Quote")
    return _serialize_quote(quote)


@router.put("/{quote_id}")
async def update_quote(quote_id: UUID, payload: QuoteUpdate, db: AsyncSession = Depends(get_db)):
    quote = await get_active_or_404(db, Quote, quote_id, "Quote")
    apply_updates(quote, payload)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{quote_id}")
async def delete_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await get_active_or_404(db, Quote, quote_id, "Quote")
    quote.deleted_at = utcnow()
    await db.commit()
    return {"status": "deleted"}


@router.post("/{quote_id}/send")
async def send_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await get_active_or_404(db, Quote, quote_id, "Quote")
    if quote.status != "draft":
        raise HTTPException(status_code=409, detail=f"Only draft quotes can be sent (current status: {quote.status})")
    quote.status = "sent"
    quote.sent_at = utcnow()
    await db.commit()
    return {"status": "sent", "quote_id": str(quote.id)}


@router.post("/{quote_id}/accept")
async def accept_quote(quote_id: UUID, db: AsyncSession = Depends(get_db)):
    quote = await get_active_or_404(db, Quote, quote_id, "Quote")
    if quote.status != "sent":
        raise HTTPException(status_code=409, detail=f"Only sent quotes can be accepted (current status: {quote.status})")
    quote.status = "accepted"
    quote.accepted_at = utcnow()
    await db.commit()
    return {"status": "accepted", "quote_id": str(quote.id)}
