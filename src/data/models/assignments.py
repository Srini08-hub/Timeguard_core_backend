from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.clients import Client
    from src.data.models.department import Department
    from src.data.models.employee import Employee


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class Assignment(Base):
    __tablename__ = "assignments"

    __table_args__ = (
        # One employee can have only one ACTIVE assignment
        Index(
            "uq_employee_active_assignment",
            "emp_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    emp_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("employees.emp_id"),
        nullable=False,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("departments.department_id"),
        nullable=False,
    )

    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(
            AssignmentStatus,
            name="assignment_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=AssignmentStatus.ACTIVE,
        server_default=AssignmentStatus.ACTIVE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    employee: Mapped[Employee] = relationship(
        back_populates="assignments",
        lazy="selectin",
    )

    client: Mapped[Client] = relationship(
        back_populates="assignments",
        lazy="selectin",
    )

    department: Mapped[Department] = relationship(
        back_populates="assignments",
        lazy="selectin",
    )
