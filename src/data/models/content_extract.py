from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.attachment import Attachment
from src.data.models.base import Base
from src.data.models.email import Email

# class ContentExtractStatus(StrEnum):
#     PENDING = "PENDING"
#     PROCESSING = "PROCESSING"
#     COMPLETED = "COMPLETED"


class ContentExtract(Base):
    __tablename__ = "content_extracts"

    __table_args__ = (
        UniqueConstraint(
            "email_id",
            "source_type",
            "attachment_id",
            name="uq_content_extract_source",
        ),
    )

    content_extract_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("emails.email_id", ondelete="CASCADE"),
        nullable=False,
    )

    attachment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("attachments.attachment_id", ondelete="CASCADE"),
        nullable=True,
    )

    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    extracted_payload: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # status: Mapped[ContentExtractStatus] = mapped_column(
    #         SQLEnum(
    #             ContentExtractStatus,
    #             name="content_extract_status",
    #             values_callable=lambda enum_cls: [status.value for status in enum_cls],
    #         ),
    #         nullable=False,
    #         server_default=ContentExtractStatus.PENDING,
    # )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    email: Mapped[Email] = relationship(
        "Email",
        back_populates="content_extracts",
    )

    attachment: Mapped[Attachment | None] = relationship(
        "Attachment",
        back_populates="content_extracts",
    )
