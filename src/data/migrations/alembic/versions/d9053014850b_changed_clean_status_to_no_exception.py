"""changed clean status to no exception

Revision ID: d9053014850b
Revises: 3aa7f099d031
Create Date: 2026-07-04 14:08:10.432791

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d9053014850b"
down_revision: Union[str, Sequence[str], None] = "3aa7f099d031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE timecard_status RENAME VALUE 'clean' TO 'no_exception'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE timecard_status RENAME VALUE 'no_exception' TO 'clean'")
