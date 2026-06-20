import uuid

from src.data.repositories.email_repository import EmailRepository
from src.schemas.attachment_schema import AttachmentInfo
from src.schemas.email_schema import TimesheetEmailResponse


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
