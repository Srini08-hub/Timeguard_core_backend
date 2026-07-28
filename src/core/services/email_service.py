import logging
import uuid
from typing import cast

from src.control.agents.graph import get_email_graph
from src.control.agents.graph_config import (
    DB_SESSION_CONFIG_KEY,
    GMAIL_SERVICE_CONFIG_KEY,
)
from src.control.agents.state import TimeguardState
from src.core.exceptions.custom_exception import ValidationException
from src.core.services.excel_extraction_strategy_service import (
    excel_extraction_strategy_service,
)
from src.core.services.gmail_service import GmailService
from src.data.models.email import EmailStatus
from src.data.repositories.email_repository import EmailRepository
from src.schemas.attachment_schema import AttachmentInfo
from src.schemas.email_schema import TimesheetEmailResponse

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, email_repository: EmailRepository) -> None:
        self.email_repository = email_repository

    async def get_timesheet_mail(self) -> list[TimesheetEmailResponse]:
        emails = await self.email_repository.get_timesheet_emails()
        # if not emails:
        #     return []
        return [
            TimesheetEmailResponse(
                email_id=email.email_id,
                sender_email=email.sender_email,
                status=email.status,
                subject=email.subject,
                body=email.body,
                failure_stage=email.failure_stage,
                failure_reason=email.failure_reason,
                received_at=email.received_at,
                # classification_status=email.classification_status,
            )
            for email in emails
        ]

    async def get_non_timesheet_mail(self) -> list[TimesheetEmailResponse]:
        emails = await self.email_repository.get_non_timesheet_emails()
        # if not emails:
        #     return None
        return [
            TimesheetEmailResponse(
                email_id=email.email_id,
                sender_email=email.sender_email,
                status=email.status,
                subject=email.subject,
                body=email.body,
                failure_stage=email.failure_stage,
                failure_reason=email.failure_reason,
                received_at=email.received_at,
                # classification_status=email.classification_status,
            )
            for email in emails
        ]

    async def get_emails_by_status(self, status: str) -> list[TimesheetEmailResponse]:

        try:
            email_status = EmailStatus(status)
        except ValueError as e:
            raise ValidationException("Invalid email status") from e
        emails = await self.email_repository.get_emails_by_status(email_status)

        return [
            TimesheetEmailResponse(
                email_id=email.email_id,
                sender_email=email.sender_email,
                status=email.status,
                subject=email.subject,
                body=email.body,
                failure_stage=email.failure_stage,
                failure_reason=email.failure_reason,
                received_at=email.received_at,
                # classification_status=email.classification_status,
            )
            for email in emails
        ]

    async def get_attachments(self, email_id: str) -> list[AttachmentInfo]:
        emailid = uuid.UUID(email_id)
        attachments = await self.email_repository.get_attachments(emailid)
        return [
            AttachmentInfo(
                attachment_id=attachment.attachment_id,
                filename=attachment.file_name,
                failure_stage=attachment.failure_stage,
                failure_reason=attachment.failure_reason,
                attachment_url=attachment.attachment_url,
                document_type=attachment.document_type,
                status=attachment.status,
            )
            for attachment in attachments
        ]

    async def retry_email(self, email_id: str) -> dict:

        email_uuid = uuid.UUID(email_id)
        email = await self.email_repository.get_by_id(email_uuid)

        if email is None:
            raise ValueError(f"Email with id {email_id} not found")

        try:
            gmail_service = GmailService()
            graph = await get_email_graph()

            # Use gmail_message_id as thread_id to resume from checkpoint
            await graph.ainvoke(
                cast(
                    TimeguardState,
                    {
                        "gmail_message_id": email.gmail_message_id,
                        "excel_extraction_strategy": (
                            excel_extraction_strategy_service.get_strategy()
                        ),
                    },
                ),
                config={
                    "configurable": {
                        DB_SESSION_CONFIG_KEY: self.email_repository._session,
                        GMAIL_SERVICE_CONFIG_KEY: gmail_service,
                        "thread_id": email.gmail_message_id,
                    }
                },
            )

            logger.info("Successfully retried email %s", email_id)
            return {
                "email_id": email_id,
                "status": "retry_initiated",
                "message": "Email retry has been initiated successfully",
            }
        except Exception as e:
            logger.exception("Failed to retry email %s: %s", email_id, e)
            raise
