from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class TimecardExceptionResponse(BaseModel):
    exception_id: UUID
    timecard_id: UUID
    severity: str
    exception_type: str
    reason: str
    resolved: bool
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimecardResponse(BaseModel):
    timecard_id: UUID
    timesheet_id: UUID
    emp_id: UUID | None = None
    assignment_id: UUID | None = None
    rule_id: UUID | None = None
    reviewed_by: UUID | None = None
    week_ending: date
    employee_name: str | None = None
    reg_hours: Decimal | None = None
    ot_hours: Decimal | None = None
    dt_hours: Decimal | None = None
    status: str
    severity: str
    review_comment: str | None = None
    created_at: datetime
    updated_at: datetime
    exceptions: list[TimecardExceptionResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TimecardUpdate(BaseModel):
    employee_name: str | None = Field(default=None, max_length=200)
    reg_hours: Decimal | None = Field(default=None, ge=0)
    ot_hours: Decimal | None = Field(default=None, ge=0)
    dt_hours: Decimal | None = Field(default=None, ge=0)
    review_comment: str | None = None
    reviewed_by: UUID | None = None


class TimecardBulkAction(BaseModel):
    timecard_ids: list[UUID]
