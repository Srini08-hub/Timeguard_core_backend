from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DepartmentCreate(BaseModel):
    client_id: UUID
    department_name: str = Field(min_length=1, max_length=200)


class DepartmentUpdate(BaseModel):
    department_name: str | None = Field(default=None, min_length=1, max_length=200)


class DepartmentResponse(BaseModel):
    department_id: UUID
    client_id: UUID
    department_name: str
    created_at: datetime

    class Config:
        from_attributes = True
