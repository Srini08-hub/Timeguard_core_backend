from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.attachment import Attachment
    from src.data.models.timesheet import Timesheet


class EmailStatus(StrEnum):
    NOT_RECEIVED = "not_received"
    RECEIVED = "received"
    CLASSIFYED = "classified"
    PROCESSED = "processed"
    # NOT_PROCESSED = "not_processed"
    FAILED = "failed"


class EmailClassificationStatus(StrEnum):
    UNKNOWN = "unknown"
    TIMESHEET = "timesheet"
    NOT_TIMESHEET = "not_timesheet"


class Email(Base):
    __tablename__ = "emails"

    email_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    gmail_message_id: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        nullable=False,
    )

    gmail_thread_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    sender_email: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    subject: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    classification_status: Mapped[EmailClassificationStatus] = mapped_column(
        SQLEnum(
            EmailClassificationStatus,
            name="email_classification_status",
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
        ),
        nullable=False,
        default=EmailClassificationStatus.UNKNOWN,
    )

    status: Mapped[EmailStatus] = mapped_column(
        SQLEnum(
            EmailStatus,
            name="email_status",
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
        ),
        nullable=False,
        default=EmailStatus.RECEIVED,
    )

    failure_stage: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    received_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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

    attachments: Mapped[list["Attachment"]] = relationship(
        "Attachment",
        back_populates="email",
        cascade="all, delete-orphan",
    )

    timesheets: Mapped[list["Timesheet"]] = relationship(
        "Timesheet",
        back_populates="email",
        cascade="all, delete-orphan",
    )
