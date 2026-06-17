from pydantic import BaseModel


class AttachmentInfo(BaseModel):
    attachment_id: str
    filename: str
    mime_type: str
    size: int | None = None


class EmailContent(BaseModel):
    message_id: str
    thread_id: str
    subject: str
    sender_name: str | None = None
    sender_email: str
    received_at: str | None = None
    body: str
    attachments: list[AttachmentInfo]
