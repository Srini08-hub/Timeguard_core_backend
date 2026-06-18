import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.email import Email, EmailClassificationStatus, EmailStatus

logger = logging.getLogger(__name__)


class EmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, email_id: UUID) -> Email | None:
        return await self._session.get(Email, email_id)

    async def get_by_gmail_message_id(self, gmail_message_id: str) -> Email | None:
        result = await self._session.execute(
            select(Email).where(Email.gmail_message_id == gmail_message_id)
        )
        return result.scalar_one_or_none()

    async def create(
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
        self._session.add(email)
        await self._session.flush()
        logger.info(
            "Created Email record %s for gmail_message_id=%s",
            email.email_id,
            gmail_message_id,
        )

        return email

    async def create_failed_fetch(
        self,
        *,
        gmail_message_id: str,
        gmail_thread_id: str = "unknown",
        failure_stage: str,
        failure_reason: str,
        received_at: datetime,
    ) -> Email:
        email = Email(
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            sender_email="",
            subject=None,
            body=None,
            status=EmailStatus.NOT_RECEIVED,
            failure_stage=failure_stage,
            failure_reason=failure_reason,
            received_at=received_at,
        )
        self._session.add(email)
        await self._session.flush()
        logger.info(
            "Created failed Email record %s for gmail_message_id=%s",
            email.email_id,
            gmail_message_id,
        )

        return email

    async def set_status(
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
        await self._session.flush()

    async def set_classification_status(
        self,
        email: Email,
        classification_status: EmailClassificationStatus,
    ) -> None:
        email.classification_status = classification_status
        await self._session.flush()
        logger.info(
            "Updated Email record %s classification_status to %s",
            email.email_id,
            classification_status,
        )
