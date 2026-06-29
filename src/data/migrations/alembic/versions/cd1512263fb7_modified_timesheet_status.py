"""modified timesheet status

Revision ID: cd1512263fb7
Revises: ed8ae0e7e6e2
Create Date: 2026-06-26 22:37:52.965539

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cd1512263fb7"
down_revision: str | Sequence[str] | None = "ed8ae0e7e6e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.execute("""
        CREATE TYPE timesheet_status_new AS ENUM (
            'pending',
            'processed'
        );
    """)

    # 1. Drop the old default
    op.execute("""
        ALTER TABLE timesheets
        ALTER COLUMN status DROP DEFAULT;
    """)

    # 2. Convert the column
    op.execute("""
        ALTER TABLE timesheets
        ALTER COLUMN status
        TYPE timesheet_status_new
        USING (
            CASE
                WHEN status::text = 'PENDING' THEN 'pending'
                WHEN status::text = 'MERGING' THEN 'processed'
                WHEN status::text = 'COMPLETED' THEN 'processed'
            END
        )::timesheet_status_new;
    """)

    # 3. Replace the enum type
    op.execute("DROP TYPE timesheet_status;")
    op.execute("ALTER TYPE timesheet_status_new RENAME TO timesheet_status;")

    # 4. Set the new default
    op.execute("""
        ALTER TABLE timesheets
        ALTER COLUMN status SET DEFAULT 'pending'::timesheet_status;
    """)


def downgrade() -> None:
    pass
