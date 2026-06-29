import uuid

from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_client_rule_service
from src.core.services.client_rule_service import ClientRuleService
from src.schemas.client_rule_schema import (
    ClientRuleCreate,
    ClientRuleResponse,
    ClientRuleUpdate,
)

router = APIRouter(prefix="/client-rules", tags=["client-rules"])


@router.post(
    "",
    response_model=ClientRuleResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule(
    payload: ClientRuleCreate,
    client_rule_service: ClientRuleService = Depends(get_client_rule_service),
) -> ClientRuleResponse:
    return await client_rule_service.create_rule(payload)


@router.get(
    "/department/{department_id}",
    response_model=list[ClientRuleResponse],
    status_code=status.HTTP_200_OK,
)
async def get_rules_by_department(
    department_id: uuid.UUID = Path(..., description="Department ID"),
    client_rule_service: ClientRuleService = Depends(get_client_rule_service),
) -> list[ClientRuleResponse]:
    return await client_rule_service.get_rules_by_department(department_id)


@router.get(
    "/{rule_id}",
    response_model=ClientRuleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_rule(
    rule_id: uuid.UUID = Path(..., description="Client rule ID"),
    client_rule_service: ClientRuleService = Depends(get_client_rule_service),
) -> ClientRuleResponse:
    return await client_rule_service.get_rule(rule_id)


@router.patch(
    "/{rule_id}",
    response_model=ClientRuleResponse,
    status_code=status.HTTP_200_OK,
)
async def update_rule(
    payload: ClientRuleUpdate,
    rule_id: uuid.UUID = Path(..., description="Client rule ID"),
    client_rule_service: ClientRuleService = Depends(get_client_rule_service),
) -> ClientRuleResponse:
    return await client_rule_service.update_rule(rule_id, payload)


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def soft_delete_rule(
    rule_id: uuid.UUID = Path(..., description="Client rule ID"),
    client_rule_service: ClientRuleService = Depends(get_client_rule_service),
) -> None:
    await client_rule_service.soft_delete_rule(rule_id)
