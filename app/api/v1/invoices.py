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
from app.models.invoice import Invoice
from app.models.user import User

router = APIRouter(prefix="/invoices", tags=["invoices"])


class InvoiceCreate(BaseModel):
    quote_id: UUID | None = None
    opportunity_id: UUID | None = None
    contact_id: UUID | None = None
    company_id: UUID | None = None
    status: str = "draft"
    subtotal: float = 0
    discount: float = 0
    tax: float = 0
    total: float = 0
    currency: str = "CRC"
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None



InvoiceUpdate = partial_model(InvoiceCreate, "InvoiceUpdate")

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
    items, total = await paginate(db, stmt, page, page_size)
    return {"items": [_serialize_invoice(item) for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_invoice(payload: InvoiceCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload.contact_id and not payload.company_id:
        raise HTTPException(status_code=400, detail="La factura requiere contact_id o company_id")

    invoice_number = await db.scalar(text("SELECT next_document_number('invoice', 'FAC')"))
    invoice = Invoice(invoice_number=invoice_number, created_by=user.id, **payload.model_dump(exclude={"issue_date", "due_date"}, exclude_none=True))
    invoice.issue_date = payload.issue_date
    invoice.due_date = payload.due_date
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return _serialize_invoice(invoice)


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await get_active_or_404(db, Invoice, invoice_id, "Invoice")
    return _serialize_invoice(invoice)


@router.put("/{invoice_id}")
async def update_invoice(invoice_id: UUID, payload: InvoiceUpdate, db: AsyncSession = Depends(get_db)):
    invoice = await get_active_or_404(db, Invoice, invoice_id, "Invoice")
    apply_updates(invoice, payload)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{invoice_id}")
async def delete_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await get_active_or_404(db, Invoice, invoice_id, "Invoice")
    invoice.deleted_at = utcnow()
    await db.commit()
    return {"status": "deleted"}


@router.post("/{invoice_id}/send")
async def send_invoice(invoice_id: UUID, db: AsyncSession = Depends(get_db)):
    invoice = await get_active_or_404(db, Invoice, invoice_id, "Invoice")
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail=f"Only draft invoices can be sent (current status: {invoice.status})")
    invoice.status = "sent"
    await db.commit()
    return {"status": "sent", "invoice_id": str(invoice.id)}
