"""add not_received email status

Revision ID: 7c2b4e0d9f1a
Revises: 320993740aa0
Create Date: 2026-06-18 12:15:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c2b4e0d9f1a"
down_revision: str | Sequence[str] | None = "320993740aa0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE email_status ADD VALUE IF NOT EXISTS 'not_received'")


def downgrade() -> None:
    pass
