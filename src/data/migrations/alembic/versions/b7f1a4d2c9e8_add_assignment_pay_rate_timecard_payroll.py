"""add assignment pay rate and timecard payroll fields

Revision ID: b7f1a4d2c9e8
Revises: 0e81e346ce4a
Create Date: 2026-06-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7f1a4d2c9e8"
down_revision: str | Sequence[str] | None = "0e81e346ce4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "assignments",
        sa.Column(
            "pay_rate",
            sa.Numeric(precision=10, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "timecards",
        sa.Column("pay_rate", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "timecards",
        sa.Column("regular_pay", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "timecards",
        sa.Column("ot_pay", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "timecards",
        sa.Column("dt_pay", sa.Numeric(precision=12, scale=2), nullable=True),
    )
    op.add_column(
        "timecards",
        sa.Column("gross_pay", sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("timecards", "gross_pay")
    op.drop_column("timecards", "dt_pay")
    op.drop_column("timecards", "ot_pay")
    op.drop_column("timecards", "regular_pay")
    op.drop_column("timecards", "pay_rate")
    op.drop_column("assignments", "pay_rate")
