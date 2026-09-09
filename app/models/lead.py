from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

LEAD_TYPE_VALUES = ("individual", "company")
LEAD_SOURCE_VALUES = ("website", "email", "whatsapp", "facebook", "instagram", "linkedin", "referral", "phone", "other")
LEAD_STATUS_VALUES = ("new", "contacted", "qualified", "unqualified", "converted", "lost")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_type: Mapped[str] = mapped_column(
        Enum(*LEAD_TYPE_VALUES, name="lead_type_enum", create_type=False), nullable=False, default="individual"
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source: Mapped[str] = mapped_column(
        Enum(*LEAD_SOURCE_VALUES, name="lead_source_enum", create_type=False), nullable=False, default="website"
    )
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*LEAD_STATUS_VALUES, name="lead_status_enum", create_type=False), nullable=False, default="new"
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
