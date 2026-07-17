"""allow matching prerequisite correction timecards

Revision ID: b4d7c2e9a8f1
Revises: 2928989b7801
Create Date: 2026-07-16 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4d7c2e9a8f1"
down_revision: Union[str, Sequence[str], None] = "2928989b7801"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_client'")
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_week_ending'")
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_department'")
    op.alter_column("timecards", "week_ending", nullable=True)


def downgrade() -> None:
    op.alter_column("timecards", "week_ending", nullable=False)
