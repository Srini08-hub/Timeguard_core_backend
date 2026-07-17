from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base
from src.data.models.exception import TimecardException


class TimecardStatus(StrEnum):
    PENDING = "pending"
    NO_EXCEPTION = "no_exception"
    EXCEPTION = "exception"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExceptionSeverity(StrEnum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Timecard(Base):
    __tablename__ = "timecards"

    # __table_args__ = (
    #     UniqueConstraint(
    #         "emp_id",
    #         "assignment_id",
    #         "week_ending",
    #         name="uq_timecard_employee_week",
    #     ),
    # )

    timecard_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    timesheet_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("timesheets.timesheet_id", ondelete="CASCADE"),
        nullable=False,
    )

    emp_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("employees.emp_id"),
        nullable=True,
    )

    assignment_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("assignments.assignment_id"),
        nullable=True,
    )

    rule_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("client_rules.rule_id"),
        nullable=True,
    )

    reviewed_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=True,
    )

    week_ending: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    employee_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )

    reg_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    ot_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    dt_hours: Mapped[Decimal | None] = mapped_column(
        Numeric(6, 2),
        nullable=True,
    )

    pay_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    regular_pay: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    ot_pay: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    dt_pay: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    gross_pay: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    status: Mapped[TimecardStatus] = mapped_column(
        SQLEnum(
            TimecardStatus,
            name="timecard_status",
            values_callable=lambda enum_cls: [status.value for status in enum_cls],
        ),
        nullable=False,
        server_default=TimecardStatus.PENDING,
    )

    severity: Mapped[ExceptionSeverity] = mapped_column(
        SQLEnum(
            ExceptionSeverity,
            name="exception_severity",
            values_callable=lambda enum_cls: [severity.value for severity in enum_cls],
        ),
        nullable=False,
        server_default=ExceptionSeverity.NONE,
    )

    review_comment: Mapped[str | None] = mapped_column(
        Text,
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

    exceptions: Mapped[list["TimecardException"]] = relationship(
        back_populates="timecard",
        cascade="all, delete-orphan",
    )
