from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class TimesheetResponse(BaseModel):
    timesheet_id: UUID
    email_id: UUID
    client_name: str | None = None
    week_ending: date | None = None
    payload: dict[str, Any] | None = None
    status: str | None = None
    created_at: datetime | None = None
