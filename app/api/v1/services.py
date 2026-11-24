from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import paginate, apply_updates, get_active_or_404, partial_model, utcnow
from app.core.database import get_db
from app.models.service import Service

router = APIRouter(prefix="/services", tags=["services"])


class ServiceCreate(BaseModel):
    name: str
    code: str
    description: str | None = None
    service_type: str = "individual"
    price: float = 0
    currency: str = "CRC"
    billing_type: str = "one_time"
    is_active: bool = True



ServiceUpdate = partial_model(ServiceCreate, "ServiceUpdate")

@router.get("")
async def list_services(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Service).where(Service.deleted_at.is_(None)).order_by(Service.name)
    items, total = await paginate(db, stmt, page, page_size)
    return {"items": [{"id": str(item.id), "name": item.name, "code": item.code, "price": str(item.price)} for item in items], "total": total, "page": page, "page_size": page_size}


@router.post("")
async def create_service(payload: ServiceCreate, db: AsyncSession = Depends(get_db)):
    service = Service(**payload.model_dump(exclude_none=True))
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return {"id": str(service.id), "status": "created"}


@router.get("/{service_id}")
async def get_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    service = await get_active_or_404(db, Service, service_id, "Service")
    return {"id": str(service.id), "name": service.name, "code": service.code, "price": str(service.price)}


@router.put("/{service_id}")
async def update_service(service_id: UUID, payload: ServiceUpdate, db: AsyncSession = Depends(get_db)):
    service = await get_active_or_404(db, Service, service_id, "Service")
    apply_updates(service, payload)
    await db.commit()
    return {"status": "updated"}


@router.delete("/{service_id}")
async def delete_service(service_id: UUID, db: AsyncSession = Depends(get_db)):
    service = await get_active_or_404(db, Service, service_id, "Service")
    service.deleted_at = utcnow()
    await db.commit()
    return {"status": "deleted"}
