"""add validation exception types

Revision ID: e01d9d5d2c10
Revises: c85ab4f4a000
Create Date: 2026-06-29 06:30:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "e01d9d5d2c10"
down_revision: str | Sequence[str] | None = "c85ab4f4a000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_employee_id'")
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'time_entry_conflict'")
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'weekly_hours_exceed_limit'")


def downgrade() -> None:
    pass
