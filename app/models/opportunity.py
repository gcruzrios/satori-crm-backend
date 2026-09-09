from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, DateTime, Enum, Numeric, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

OPPORTUNITY_STATUS_VALUES = ("open", "won", "lost")


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pipeline_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipelines.id"), nullable=False)
    stage_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pipeline_stages.id"), nullable=False)
    lead_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    contact_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    expected_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CRC")
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*OPPORTUNITY_STATUS_VALUES, name="opportunity_status_enum", create_type=False), nullable=False, default="open"
    )
    assigned_to: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"), onupdate=text("now()"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
