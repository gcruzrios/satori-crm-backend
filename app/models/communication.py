from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

COMM_CHANNEL_VALUES = ("email", "whatsapp", "phone", "web")
COMM_DIRECTION_VALUES = ("inbound", "outbound")
COMM_STATUS_VALUES = ("queued", "sent", "delivered", "read", "failed")


class Communication(Base):
    __tablename__ = "communications"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    channel: Mapped[str] = mapped_column(Enum(*COMM_CHANNEL_VALUES, name="comm_channel_enum", create_type=False), nullable=False)
    direction: Mapped[str] = mapped_column(Enum(*COMM_DIRECTION_VALUES, name="comm_direction_enum", create_type=False), nullable=False)
    lead_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    contact_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=True)
    company_id: Mapped[UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(Enum(*COMM_STATUS_VALUES, name="comm_status_enum", create_type=False), nullable=False, default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))
