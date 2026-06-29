"""addded exception type

Revision ID: 852125786eaf
Revises: e01d9d5d2c10
Create Date: 2026-06-29 15:43:46.813739

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "852125786eaf"
down_revision: Union[str, Sequence[str], None] = "e01d9d5d2c10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_employee_id';")
    op.execute("ALTER TYPE exception_type ADD VALUE IF NOT EXISTS 'missing_assignment_id';")


def downgrade() -> None:
    # PostgreSQL does not support DROP VALUE from an enum.
    # Downgrading would require recreating the enum type.
    pass
