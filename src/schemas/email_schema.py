from uuid import UUID

from pydantic import BaseModel

from src.data.models.email import EmailStatus

# class AttachmentInfo(BaseModel):
#     attachment_id: str
#     filename: str
#     mime_type: str
#     size: int | None = None


# class EmailContent(BaseModel):
#     message_id: str
#     thread_id: str
#     subject: str
#     sender_name: str | None = None
#     sender_email: str
#     received_at: str | None = None
#     body: str
#     attachments: list[AttachmentInfo]


class TimesheetEmailResponse(BaseModel):
    email_id: UUID
    sender_email: str
    subject: str | None = None
    body: str | None = None
    status: EmailStatus
