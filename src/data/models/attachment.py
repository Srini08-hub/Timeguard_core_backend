# from __future__ import annotations
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.content_extract import ContentExtract
    from src.data.models.email import Email


class AttachmentStatus(StrEnum):
    PENDING = "pending"
    TIMESHEET = "timesheet"
    NOT_TIMESHEET = "not_timesheet"
    EXTRACTED = "extracted"
    # NOT_PROCESSED = "not_processed"
    FAILED = "failed"


class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("emails.email_id", ondelete="CASCADE"),
        nullable=False,
    )

    attachment_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    document_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    status: Mapped[AttachmentStatus] = mapped_column(
        SQLEnum(
            AttachmentStatus,
            name="attachment_status",
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
        ),
        nullable=False,
        default=AttachmentStatus.PENDING,
    )

    failure_stage: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    email: Mapped["Email"] = relationship(
        "Email",
        back_populates="attachments",
    )
    content_extracts: Mapped[list["ContentExtract"]] = relationship(
        "ContentExtract",
        back_populates="attachment",
        cascade="all, delete-orphan",
    )
