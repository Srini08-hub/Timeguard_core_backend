from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.data.models.base import Base

if TYPE_CHECKING:
    from src.data.models.assignments import Assignment
    from src.data.models.department import Department


class Client(Base):
    __tablename__ = "clients"

    client_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    client_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    sender_email: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    sender_domain: Mapped[str] = mapped_column(
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

    created_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.user_id"),
        nullable=False,
    )

    departments: Mapped[list[Department]] = relationship(
        back_populates="client",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="client",
        lazy="selectin",
    )
