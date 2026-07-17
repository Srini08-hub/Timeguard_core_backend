from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.timecard import Timecard


class ExceptionSeverity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExceptionType(StrEnum):
    MISSING_EMPLOYEE_ID = "missing_employee_id"
    MISSING_ASSIGNMENT_ID = "missing_assignment_id"
    MISSING_CLIENT = "missing_client"
    MISSING_WEEK_ENDING = "missing_week_ending"
    MISSING_DEPARTMENT = "missing_department"
    HOURS_EXCEED_LIMIT = "hours_exceed_limit"
    WEEKLY_HOURS_EXCEED_LIMIT = "weekly_hours_exceed_limit"
    LOW_CONFIDENCE = "low_confidence"
    CALCULATION_DISCREPANCY = "calculation_discrepancy"
    TIME_ENTRY_CONFLICT = "time_entry_conflict"
    MISSING_TIME_ENTRY = "missing_time_entry"


class TimecardException(Base):
    __tablename__ = "exceptions"

    exception_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    timecard_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("timecards.timecard_id", ondelete="CASCADE"),
        nullable=False,
    )

    severity: Mapped[ExceptionSeverity] = mapped_column(
        SQLEnum(
            ExceptionSeverity,
            name="exception_severity",
            values_callable=lambda enum_cls: [severity.value for severity in enum_cls],
        ),
        nullable=False,
    )

    exception_type: Mapped[ExceptionType] = mapped_column(
        SQLEnum(
            ExceptionType,
            name="exception_type",
            values_callable=lambda enum_cls: [exc_type.value for exc_type in enum_cls],
        ),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    resolved: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
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

    timecard: Mapped["Timecard"] = relationship(
        back_populates="exceptions",
    )
