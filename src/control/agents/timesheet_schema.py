"""Canonical timesheet extraction schema shared by extraction and merge nodes."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class TimesheetRecord(BaseModel):
    """Timesheet record in timesheet."""

    date: str | None = Field(description="Date in YYYY-MM-DD format")
    check_in: str | None = Field(default=None, description="Check-in time in HH:MM format")
    check_out: str | None = Field(default=None, description="Check-out time in HH:MM format")
    break_hour: str | None = Field(default=None, description="Break time in HH:MM format")
    hours: str | None = Field(default=None, description="Daily Hours worked")
    total_hours: str | None = Field(default=None, description="Total Hours worked")
    overtime_hours: str | None = Field(default=None, description="Overtime hours")
    confidence: float | None = Field(default=None, description="Confidence score")

    @field_validator("confidence", mode="before")
    @classmethod
    def coerce_confidence(cls, v: Any) -> float | None:
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None


class SourceInfo(BaseModel):
    """Source information for employee record."""

    file_name: str = Field(description="File name")
    content_type: str = Field(description="Content type (excel, pdf, email)")


class EmployeeRecord(BaseModel):
    """Employee record in timesheet."""

    employee_name: str = Field(description="Employee name")
    department: str | None = Field(default=None, description="Department")
    source: list[SourceInfo] = Field(description="Source information")
    timesheet_records: list[TimesheetRecord] = Field(description="Timesheet records")


class GlobalData(BaseModel):
    """Global timesheet data."""

    client_name: str | None = Field(default=None, description="Client name")
    week_ending: str | None = Field(default=None, description="Week ending date")


class MergeResponse(BaseModel):
    """Structured response from timesheet extraction and merge LLMs."""

    global_data: GlobalData = Field(description="Global timesheet data")
    employee_records: list[EmployeeRecord] = Field(description="Employee records")
