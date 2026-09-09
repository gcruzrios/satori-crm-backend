from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

ACTIVITY_TYPE_VALUES = ("call", "email", "whatsapp", "meeting", "task", "note", "follow_up")
ACTIVITY_STATUS_VALUES = ("pending", "completed", "cancelled")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    type: Mapped[str] = mapped_column(
        Enum(*ACTIVITY_TYPE_VALUES, name="activity_type_enum", create_type=False), nullable=False, default="task"
    )
    # DB column is "subject"; kept as `title` on the Python side to match the existing API contract.
    title: Mapped[str] = mapped_column("subject", String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    contact_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    opportunity_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True)
    assigned_to: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(*ACTIVITY_STATUS_VALUES, name="activity_status_enum", create_type=False), nullable=False, default="pending"
    )
    # DB column is "due_date" (timestamptz); kept as `due_at` on the Python side to match the existing API contract.
    due_at: Mapped[datetime | None] = mapped_column("due_date", DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
