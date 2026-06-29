from uuid import UUID

from src.core.exceptions.custom_exception import (
    ConflictException,
    DatabaseException,
    ResourceNotFound,
)
from src.data.models.client_rules import ClientRule
from src.data.repositories.client_repository import ClientRepository
from src.data.repositories.client_rule_repository import ClientRuleRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.schemas.client_rule_schema import (
    ClientRuleCreate,
    ClientRuleResponse,
    ClientRuleUpdate,
)


class ClientRuleService:
    def __init__(
        self,
        client_rule_repository: ClientRuleRepository,
        client_repository: ClientRepository,
        department_repository: DepartmentRepository,
    ) -> None:
        self._client_rule_repository = client_rule_repository
        self._client_repository = client_repository
        self._department_repository = department_repository

    async def create_rule(self, payload: ClientRuleCreate) -> ClientRuleResponse:
        await self._validate_client_department(
            payload.client_id,
            payload.department_id,
        )
        await self._ensure_unique_active_rule(
            payload.client_id,
            payload.department_id,
        )

        try:
            rule = await self._client_rule_repository.create(
                client_id=payload.client_id,
                department_id=payload.department_id,
                weekly_ot_threshold=payload.weekly_ot_threshold,
                weekly_dt_threshold=payload.weekly_dt_threshold,
                ot_multiplier=payload.ot_multiplier,
                dt_multiplier=payload.dt_multiplier,
                break_deduction_hrs=payload.break_deduction_hrs,
                break_auto_deduct=payload.break_auto_deduct,
            )
            return self._to_response(rule)
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to create client rule") from exc

    async def get_rule(self, rule_id: UUID) -> ClientRuleResponse:
        rule = await self._client_rule_repository.get_active_by_id(rule_id)
        if rule is None:
            raise ResourceNotFound("Client rule not found")
        return self._to_response(rule)

    async def get_rules_by_department(
        self,
        department_id: UUID,
    ) -> list[ClientRuleResponse]:
        department = await self._department_repository.get_by_id(department_id)
        if department is None or not department.is_active:
            raise ResourceNotFound("Department not found")

        rules = await self._client_rule_repository.get_active_by_department(
            department_id,
        )
        return [self._to_response(rule) for rule in rules]

    async def update_rule(
        self,
        rule_id: UUID,
        payload: ClientRuleUpdate,
    ) -> ClientRuleResponse:
        rule = await self._client_rule_repository.get_active_by_id(rule_id)
        if rule is None:
            raise ResourceNotFound("Client rule not found")

        client_id = payload.client_id or rule.client_id
        department_id = payload.department_id or rule.department_id
        await self._validate_client_department(client_id, department_id)
        await self._ensure_unique_active_rule(
            client_id,
            department_id,
            exclude_rule_id=rule_id,
        )

        fields_set = payload.model_fields_set

        try:
            updated_rule = await self._client_rule_repository.update(
                rule,
                client_id=client_id,
                department_id=department_id,
                weekly_ot_threshold=(
                    payload.weekly_ot_threshold
                    if payload.weekly_ot_threshold is not None
                    else rule.weekly_ot_threshold
                ),
                weekly_dt_threshold=(
                    payload.weekly_dt_threshold
                    if "weekly_dt_threshold" in fields_set
                    else rule.weekly_dt_threshold
                ),
                ot_multiplier=(
                    payload.ot_multiplier
                    if payload.ot_multiplier is not None
                    else rule.ot_multiplier
                ),
                dt_multiplier=(
                    payload.dt_multiplier
                    if payload.dt_multiplier is not None
                    else rule.dt_multiplier
                ),
                break_deduction_hrs=(
                    payload.break_deduction_hrs
                    if "break_deduction_hrs" in fields_set
                    else rule.break_deduction_hrs
                ),
                break_auto_deduct=(
                    payload.break_auto_deduct
                    if payload.break_auto_deduct is not None
                    else rule.break_auto_deduct
                ),
            )
            return self._to_response(updated_rule)
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to update client rule") from exc

    async def soft_delete_rule(self, rule_id: UUID) -> None:
        rule = await self._client_rule_repository.get_active_by_id(rule_id)
        if rule is None:
            raise ResourceNotFound("Client rule not found")

        try:
            await self._client_rule_repository.soft_delete(rule)
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to delete client rule") from exc

    async def _validate_client_department(
        self,
        client_id: UUID,
        department_id: UUID,
    ) -> None:
        client = await self._client_repository.get_by_id(client_id)
        if client is None or not client.is_active:
            raise ResourceNotFound("Client not found")

        department = await self._department_repository.get_by_id(department_id)
        if department is None or not department.is_active:
            raise ResourceNotFound("Department not found")
        if department.client_id != client_id:
            raise ConflictException("Department does not belong to this client")

    async def _ensure_unique_active_rule(
        self,
        client_id: UUID,
        department_id: UUID,
        *,
        exclude_rule_id: UUID | None = None,
    ) -> None:
        existing_rule = await self._client_rule_repository.get_active_by_client_department(
            client_id,
            department_id,
        )
        if existing_rule is None:
            return
        if exclude_rule_id is not None and existing_rule.rule_id == exclude_rule_id:
            return
        raise ConflictException("Active rule already exists for this department")

    def _to_response(self, rule: ClientRule) -> ClientRuleResponse:
        return ClientRuleResponse(
            rule_id=rule.rule_id,
            client_id=rule.client_id,
            department_id=rule.department_id,
            weekly_ot_threshold=rule.weekly_ot_threshold,
            weekly_dt_threshold=rule.weekly_dt_threshold,
            ot_multiplier=rule.ot_multiplier,
            dt_multiplier=rule.dt_multiplier,
            break_deduction_hrs=rule.break_deduction_hrs,
            break_auto_deduct=rule.break_auto_deduct,
            is_active=rule.is_active,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )
