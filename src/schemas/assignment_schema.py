from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AssignmentCreate(BaseModel):
    emp_id: UUID
    client_id: UUID
    department_id: UUID


class AssignmentUpdate(BaseModel):
    status: AssignmentStatus | None = None


class AssignmentResponse(BaseModel):
    assignment_id: UUID
    emp_id: UUID
    client_id: UUID
    department_id: UUID
    status: AssignmentStatus
    created_at: datetime

    class Config:
        from_attributes = True
