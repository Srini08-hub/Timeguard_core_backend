from pydantic import BaseModel, Field


class PollingStartRequest(BaseModel):
    interval_seconds: int = Field(ge=1, le=3600)


class PollingStatusResponse(BaseModel):
    running: bool
    interval_seconds: int | None = None
