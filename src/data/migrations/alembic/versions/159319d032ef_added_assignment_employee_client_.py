"""added assignment,employee,client,department tab

Revision ID: 159319d032ef
Revises: c0f7c5936658
Create Date: 2026-06-23 20:19:49.941446

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "159319d032ef"
down_revision: str | Sequence[str] | None = "c0f7c5936658"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # clients
    op.alter_column(
        "clients",
        "client_name",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    op.alter_column(
        "clients",
        "sender_email",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    op.alter_column(
        "clients",
        "sender_domain",
        existing_type=sa.String(length=200),
        nullable=False,
    )

    op.alter_column(
        "clients",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default="true",
    )

    op.alter_column(
        "clients",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.alter_column(
        "clients",
        "created_by",
        existing_type=sa.UUID(),
        nullable=False,
    )

    # employees
    op.alter_column(
        "employees",
        "name",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "employees",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default="true",
    )

    op.alter_column(
        "employees",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )

    op.alter_column(
        "employees",
        "created_by",
        existing_type=sa.UUID(),
        nullable=False,
    )  #
