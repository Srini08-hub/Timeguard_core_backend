from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.assignments import Assignment
    from src.data.models.clients import Client


class Department(Base):
    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "department_name",
            name="uq_department_client_name",
        ),
    )

    department_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clients.client_id"),
        nullable=False,
    )

    department_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    client: Mapped[Client] = relationship(
        back_populates="departments",
        lazy="selectin",
    )

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="department",
        lazy="selectin",
    )
