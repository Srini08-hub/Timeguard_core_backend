import logging
from datetime import datetime

from sqlalchemy.orm import Session

from src.data.models.email import Email, EmailStatus

logger = logging.getLogger(__name__)


class EmailRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_gmail_message_id(self, gmail_message_id: str) -> Email | None:
        return (
            self._db.query(Email)
            .filter(Email.gmail_message_id == gmail_message_id)
            .first()
        )

    def create(
        self,
        *,
        gmail_message_id: str,
        gmail_thread_id: str,
        sender_email: str,
        subject: str | None,
        body: str | None,
        received_at: datetime,
    ) -> Email:
        email = Email(
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            sender_email=sender_email,
            subject=subject,
            body=body,
            status=EmailStatus.RECEIVED,
            received_at=received_at,
        )
        self._db.add(email)
        self._db.flush()  # get email_id without committing
        logger.info(
            "Created Email record %s for gmail_message_id=%s",
            email.email_id,
            gmail_message_id,
        )

        return email

    def set_status(
        self,
        email: Email,
        status: EmailStatus,
        *,
        failure_stage: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        email.status = status
        if failure_stage:
            email.failure_stage = failure_stage
        if failure_reason:
            email.failure_reason = failure_reason
        self._db.flush()
