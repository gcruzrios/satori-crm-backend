from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.invoice import Invoice

router = APIRouter(prefix="/invoices", tags=["invoices"])


class InvoiceCreate(BaseModel):
    quote_id: str | None = None
    opportunity_id: str | None = None
    contact_id: str | None = None
    company_id: str | None = None
    status: str = "draft"
    subtotal: float = 0
    discount: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "CRC"
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


def _serialize_invoice(invoice: Invoice) -> dict:
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "quote_id": str(invoice.quote_id) if invoice.quote_id else None,
        "opportunity_id": str(invoice.opportunity_id) if invoice.opportunity_id else None,
        "contact_id": str(invoice.contact_id) if invoice.contact_id else None,
        "company_id": str(invoice.company_id) if invoice.company_id else None,
        "status": invoice.status,
        "subtotal": str(invoice.subtotal),
        "discount": str(invoice.discount),
        "tax": str(invoice.tax),
        "total": str(invoice.total),
        "currency": invoice.currency,
        "issue_date": invoice.issue_date.isoformat() if invoice.issue_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "paid_date": invoice.paid_date.isoformat() if invoice.paid_date else None,
        "notes": invoice.notes,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "updated_at": invoice.updated_at.isoformat() if invoice.updated_at else None,
    }


@router.get("")
async def list_invoices(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Invoice).where(Invoice.deleted_at.is_(None)).order_by(Invoice.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(stmt)
    items = result.scalars().all()
    return {"items": [_serialize_invoice(item) for item in items], "page": page, "page_size": page_size}


@router.post("")
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    if not payload.contact_id and not payload.company_id:
        raise HTTPException(status_code=400, detail="La factura requiere contact_id o company_id")

    invoice_number = await db.scalar(text("SELECT next_document_number('invoice', 'FAC')"))
    invoice = Invoice(invoice_number=invoice_number, **payload.model_dump(exclude={"issue_date", "due_date"}, exclude_none=True))
    invoice.issue_date = payload.issue_date
    invoice.due_date = payload.due_date
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return _serialize_invoice(invoice)


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return _serialize_invoice(invoice)


@router.put("/{invoice_id}")
async def update_invoice(invoice_id: UUID, payload: InvoiceCreate, db: AsyncSession = Depends(get_db)):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, field, value)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{invoice_id}/send")
async def send_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = "sent"
    await db.commit()
    return {"status": "sent", "invoice_id": str(invoice.id)}
