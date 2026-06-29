from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ClientRuleCreate(BaseModel):
    client_id: UUID
    department_id: UUID
    weekly_ot_threshold: Decimal = Field(default=Decimal("40"), ge=0)
    weekly_dt_threshold: Decimal | None = Field(default=None, ge=0)
    ot_multiplier: Decimal = Field(default=Decimal("1.5"), ge=0)
    dt_multiplier: Decimal = Field(default=Decimal("2.0"), ge=0)
    break_deduction_hrs: Decimal | None = Field(default=None, ge=0)
    break_auto_deduct: bool = False


class ClientRuleUpdate(BaseModel):
    client_id: UUID | None = None
    department_id: UUID | None = None
    weekly_ot_threshold: Decimal | None = Field(default=None, ge=0)
    weekly_dt_threshold: Decimal | None = Field(default=None, ge=0)
    ot_multiplier: Decimal | None = Field(default=None, ge=0)
    dt_multiplier: Decimal | None = Field(default=None, ge=0)
    break_deduction_hrs: Decimal | None = Field(default=None, ge=0)
    break_auto_deduct: bool | None = None


class ClientRuleResponse(BaseModel):
    rule_id: UUID
    client_id: UUID
    department_id: UUID
    weekly_ot_threshold: Decimal
    weekly_dt_threshold: Decimal | None
    ot_multiplier: Decimal
    dt_multiplier: Decimal
    break_deduction_hrs: Decimal | None
    break_auto_deduct: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
