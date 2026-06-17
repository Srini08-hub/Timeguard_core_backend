from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from src.data.models.base import Base


class EmailPoolState(Base):
    __tablename__ = "email_pool_state"

    mailbox_address: Mapped[str] = mapped_column(
        String(200),
        primary_key=True,
    )

    last_history_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
