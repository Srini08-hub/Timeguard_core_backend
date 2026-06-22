from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class TimesheetResponse(BaseModel):
    timesheet_id: UUID
    email_id: UUID
    attachment_id: UUID | None = None
    source_type: str
    client_name: str | None = None
    week_ending: date | None = None
    extracted_payload: dict[str, Any] | None | list[dict[str, Any]] = None
    status: str
    created_at: datetime
