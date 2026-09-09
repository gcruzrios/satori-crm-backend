from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SERVICE_TYPE_VALUES = ("individual", "corporate", "workshop", "consulting", "therapy", "assessment", "other")
BILLING_TYPE_VALUES = ("one_time", "hourly", "session", "monthly", "custom")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    service_type: Mapped[str] = mapped_column(
        Enum(*SERVICE_TYPE_VALUES, name="service_type_enum", create_type=False), nullable=False, default="individual"
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CRC")
    billing_type: Mapped[str] = mapped_column(
        Enum(*BILLING_TYPE_VALUES, name="billing_type_enum", create_type=False), nullable=False, default="one_time"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
