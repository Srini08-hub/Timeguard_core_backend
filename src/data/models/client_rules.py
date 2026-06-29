from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.data.models.base import Base


class ClientRule(Base):
    __tablename__ = "client_rules"

    rule_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    client_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clients.client_id", ondelete="CASCADE"),
        nullable=False,
    )

    department_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("departments.department_id", ondelete="CASCADE"),
        nullable=False,
    )

    weekly_ot_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="40",
    )

    weekly_dt_threshold: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )

    ot_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        server_default="1.5",
    )

    dt_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(4, 2),
        nullable=False,
        server_default="2.0",
    )

    break_deduction_hrs: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2),
        nullable=True,
    )

    break_auto_deduct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
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
