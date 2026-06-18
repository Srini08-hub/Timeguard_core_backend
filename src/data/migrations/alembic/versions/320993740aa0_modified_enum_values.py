"""modified enum values

Revision ID: 320993740aa0
Revises: fa4429c33cee
Create Date: 2026-06-18 10:33:38.536869

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "320993740aa0"
down_revision: str | Sequence[str] | None = "fa4429c33cee"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Define old and new structures for casting mapping
# Email Statuses
OLD_EMAIL_STATUSES = [
    "received",
    "classifying",
    "timesheet_detected",
    "not_timesheet",
    "processing",
    "processed",
    "failed",
]
NEW_EMAIL_STATUSES = [
    "not_received",
    "received",
    "classified",
    "processed",
    "not_processed",
    "failed",
]

# Attachment Statuses
OLD_ATTACHMENT_STATUSES = [
    "pending",
    "timesheet",
    "not_timesheet",
    "processing",
    "processed",
    "failed",
]
NEW_ATTACHMENT_STATUSES = [
    "pending",
    "timesheet",
    "not_timesheet",
    "processed",
    "not_processed",
    "failed",
]


def upgrade() -> None:
    # --- 1. RENAME OLD ENUMS ---
    op.execute("ALTER TYPE email_status RENAME TO email_status_old")
    op.execute("ALTER TYPE attachment_status RENAME TO attachment_status_old")

    # --- 2. CREATE NEW ENUMS ---
    new_email_enum = postgresql.ENUM(*NEW_EMAIL_STATUSES, name="email_status")
    new_email_enum.create(op.get_bind(), checkfirst=False)

    new_attachment_enum = postgresql.ENUM(
        *NEW_ATTACHMENT_STATUSES, name="attachment_status"
    )
    new_attachment_enum.create(op.get_bind(), checkfirst=False)

    # --- 3. ALTER COLUMNS WITH EXPLICIT DATA MAPPING ---
    # Convert Email Status
    op.execute(
        """
        ALTER TABLE emails 
        ALTER COLUMN status TYPE email_status 
        USING CASE status::text
            WHEN 'classifying' THEN 'classified'::email_status
            WHEN 'timesheet_detected' THEN 'classified'::email_status
            WHEN 'not_timesheet' THEN 'not_processed'::email_status
            WHEN 'processing' THEN 'classified'::email_status
            WHEN 'processed' THEN 'processed'::email_status
            WHEN 'failed' THEN 'failed'::email_status
            WHEN 'not_received' THEN 'not_received'::email_status
            ELSE 'received'::email_status
        END
        """
    )

    # Convert Attachment Status
    op.execute(
        """
        ALTER TABLE attachments 
        ALTER COLUMN status TYPE attachment_status 
        USING CASE status::text
            WHEN 'processing' THEN 'timesheet'::attachment_status
            WHEN 'processed' THEN 'processed'::attachment_status
            WHEN 'failed' THEN 'failed'::attachment_status
            WHEN 'not_timesheet' THEN 'not_timesheet'::attachment_status
            WHEN 'timesheet' THEN 'timesheet'::attachment_status
            ELSE 'pending'::attachment_status
        END
        """
    )

    # --- 4. DROP OLD ENUMS ---
    op.execute("DROP TYPE email_status_old")
    op.execute("DROP TYPE attachment_status_old")


def downgrade() -> None:
    # --- 1. RENAME CURRENT ENUMS ---
    op.execute("ALTER TYPE email_status RENAME TO email_status_new")
    op.execute("ALTER TYPE attachment_status RENAME TO attachment_status_new")

    # --- 2. RE-CREATE OLD ENUMS ---
    old_email_enum = postgresql.ENUM(*OLD_EMAIL_STATUSES, name="email_status")
    old_email_enum.create(op.get_bind(), checkfirst=False)

    old_attachment_enum = postgresql.ENUM(
        *OLD_ATTACHMENT_STATUSES, name="attachment_status"
    )
    old_attachment_enum.create(op.get_bind(), checkfirst=False)

    # --- 3. REVERT COLUMNS WITH EXPLICIT DATA MAPPING ---
    op.execute(
        """
        ALTER TABLE emails 
        ALTER COLUMN status TYPE email_status 
        USING CASE status::text
            WHEN 'classified' THEN 'classifying'::email_status
            WHEN 'not_processed' THEN 'not_timesheet'::email_status
            WHEN 'not_received' THEN 'failed'::email_status
            WHEN 'processed' THEN 'processed'::email_status
            WHEN 'failed' THEN 'failed'::email_status
            ELSE 'received'::email_status
        END
        """
    )

    op.execute(
        """
        ALTER TABLE attachments 
        ALTER COLUMN status TYPE attachment_status 
        USING CASE status::text
            WHEN 'not_processed' THEN 'failed'::attachment_status
            WHEN 'timesheet' THEN 'timesheet'::attachment_status
            WHEN 'not_timesheet' THEN 'not_timesheet'::attachment_status
            WHEN 'processed' THEN 'processed'::attachment_status
            WHEN 'failed' THEN 'failed'::attachment_status
            ELSE 'pending'::attachment_status
        END
        """
    )

    # --- 4. DROP NEW ENUMS ---
    op.execute("DROP TYPE email_status_new")
    op.execute("DROP TYPE attachment_status_new")
