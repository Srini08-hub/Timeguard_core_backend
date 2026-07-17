from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EmployeeCreate(BaseModel):
    email: str
    name: str = Field(min_length=1, max_length=100)
    created_by: UUID


class EmployeeUpdate(BaseModel):
    email: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)


class EmployeeResponse(BaseModel):
    emp_id: UUID
    email: str
    name: str
    is_active: bool
    is_assigned: bool
    client_id: UUID | None = None
    department_id: UUID | None = None
    created_at: datetime
