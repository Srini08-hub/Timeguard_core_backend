# from __future__ import annotations

# from datetime import date, datetime
# from typing import Any
# from uuid import UUID, uuid4

# from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
# from sqlalchemy.dialects.postgresql import JSONB
# from sqlalchemy.dialects.postgresql import UUID as PG_UUID
# from sqlalchemy.orm import Mapped, mapped_column, relationship

# from src.data.models.attachment import Attachment
# from src.data.models.base import Base
# from src.data.models.email import Email


# class Timesheet(Base):
#     __tablename__ = "timesheets"

#     __table_args__ = (
#         UniqueConstraint(
#             "email_id",
#             "source_type",
#             "attachment_id",
#             name="uq_timesheet_source",
#         ),
#     )

#     timesheet_id: Mapped[UUID] = mapped_column(
#         PG_UUID(as_uuid=True),
#         primary_key=True,
#         default=uuid4,
#     )

#     email_id: Mapped[UUID] = mapped_column(
#         PG_UUID(as_uuid=True),
#         ForeignKey("emails.email_id", ondelete="CASCADE"),
#         nullable=False,
#     )

#     attachment_id: Mapped[UUID | None] = mapped_column(
#         PG_UUID(as_uuid=True),
#         ForeignKey("attachments.attachment_id", ondelete="CASCADE"),
#         nullable=True,
#     )

#     source_type: Mapped[str] = mapped_column(String(50), nullable=False)

#     client_name: Mapped[str | None] = mapped_column(
#         String(255),
#         nullable=True,
#     )

#     week_ending: Mapped[date | None] = mapped_column(
#         Date,
#         nullable=True,
#     )

#     extracted_payload: Mapped[dict[str, Any] | None] = mapped_column(
#         JSONB,
#         nullable=True,
#     )

#     status: Mapped[str] = mapped_column(
#         String(50),
#         nullable=False,
#         server_default="pending",
#     )

#     created_at: Mapped[datetime] = mapped_column(
#         DateTime(timezone=True),
#         server_default=func.now(),
#         nullable=False,
#     )

#     email: Mapped[Email] = relationship(
#         "Email",
#         back_populates="timesheets",
#     )

#     attachment: Mapped[Attachment | None] = relationship(
#         "Attachment",
#         back_populates="timesheets",
#     )


from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.data.models.base import Base

from .email import Email


class TimesheetStatus(StrEnum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    PROCESSED = "processed"


class Timesheet(Base):
    __tablename__ = "timesheets"

    __table_args__ = (
        UniqueConstraint(
            "email_id",
            name="uq_timesheet_email",
        ),
    )

    timesheet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    email_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("emails.email_id", ondelete="CASCADE"),
        nullable=False,
    )

    client_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    week_ending: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    status: Mapped[TimesheetStatus] = mapped_column(
        SQLEnum(
            TimesheetStatus,
            name="timesheet_status",
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
        ),
        nullable=False,
        server_default=TimesheetStatus.PENDING,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    email: Mapped["Email"] = relationship(
        "Email",
        back_populates="timesheet",
    )
