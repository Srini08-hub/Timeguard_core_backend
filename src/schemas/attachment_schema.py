from uuid import UUID

from pydantic import BaseModel

from src.data.models.attachment import AttachmentStatus


class AttachmentInfo(BaseModel):
    attachment_id: UUID
    filename: str
    failure_stage: str | None = None
    failure_reason: str | None = None
    attachment_url: str
    document_type: str
    status: AttachmentStatus
