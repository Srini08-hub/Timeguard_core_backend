"""added email classification enum values

Revision ID: 3c08bdd78058
Revises: 7c2b4e0d9f1a
Create Date: 2026-06-18 18:55:36.837249

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3c08bdd78058"
down_revision: str | Sequence[str] | None = "7c2b4e0d9f1a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    classification_enum = sa.Enum(
        "unknown",
        "timesheet",
        "not_timesheet",
        name="email_classification_status",
    )

    classification_enum.create(
        op.get_bind(),
        checkfirst=True,
    )

    op.add_column(
        "emails",
        sa.Column(
            "classification_status",
            classification_enum,
            nullable=False,
            server_default="unknown",
        ),
    )

    op.alter_column(
        "emails",
        "classification_status",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column(
        "emails",
        "classification_status",
    )

    classification_enum = sa.Enum(
        "unknown",
        "timesheet",
        "not_timesheet",
        name="email_classification_status",
    )

    classification_enum.drop(
        op.get_bind(),
        checkfirst=True,
    )
