"""addded exception type

Revision ID: 0e81e346ce4a
Revises: 852125786eaf
Create Date: 2026-06-29 15:48:53.065141

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0e81e346ce4a"
down_revision: Union[str, Sequence[str], None] = "852125786eaf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE email_status ADD VALUE IF NOT EXISTS 'processed';")


def downgrade() -> None:
    pass
