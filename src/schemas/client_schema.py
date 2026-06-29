from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    client_name: str = Field(min_length=1, max_length=200)
    sender_email: str
    sender_domain: str
    created_by: UUID


class ClientUpdate(BaseModel):
    client_name: str | None = Field(None, min_length=1, max_length=200)
    sender_email: str | None = None
    sender_domain: str | None = None


class ClientResponse(BaseModel):
    client_id: UUID
    client_name: str
    sender_email: str
    sender_domain: str
    is_active: bool
    created_at: datetime
