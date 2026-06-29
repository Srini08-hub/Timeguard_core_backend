from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from src.data.models.email import EmailStatus


class TimesheetEmailResponse(BaseModel):
    email_id: UUID
    sender_email: str
    subject: str | None = None
    body: str | None = None
    status: EmailStatus
    failure_stage: str | None = None
    failure_reason: str | None = None
    received_at: datetime
