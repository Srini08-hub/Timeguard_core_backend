from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class AssignmentCreate(BaseModel):
    emp_id: UUID
    client_id: UUID
    department_id: UUID
    pay_rate: Decimal = Field(gt=0)


class AssignmentUpdate(BaseModel):
    status: AssignmentStatus | None = None
    pay_rate: Decimal | None = Field(default=None, gt=0)


class AssignmentResponse(BaseModel):
    assignment_id: UUID
    emp_id: UUID
    client_id: UUID
    department_id: UUID
    pay_rate: Decimal
    status: AssignmentStatus
    created_at: datetime

    class Config:
        from_attributes = True
