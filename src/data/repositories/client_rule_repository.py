from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.custom_exception import DatabaseException
from src.data.models.client_rules import ClientRule


class ClientRuleRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(
        self,
        *,
        client_id: UUID,
        department_id: UUID,
        weekly_ot_threshold: Decimal,
        weekly_dt_threshold: Decimal | None,
        ot_multiplier: Decimal,
        dt_multiplier: Decimal,
        break_deduction_hrs: Decimal | None,
        break_auto_deduct: bool,
    ) -> ClientRule:
        try:
            rule = ClientRule(
                client_id=client_id,
                department_id=department_id,
                weekly_ot_threshold=weekly_ot_threshold,
                weekly_dt_threshold=weekly_dt_threshold,
                ot_multiplier=ot_multiplier,
                dt_multiplier=dt_multiplier,
                break_deduction_hrs=break_deduction_hrs,
                break_auto_deduct=break_auto_deduct,
            )
            self._db_session.add(rule)
            await self._db_session.flush()
            return rule
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to create client rule") from err

    async def get_active_by_id(self, rule_id: UUID) -> ClientRule | None:
        result = await self._db_session.execute(
            select(ClientRule).where(
                ClientRule.rule_id == rule_id,
                ClientRule.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_client_department(
        self,
        client_id: UUID,
        department_id: UUID,
    ) -> ClientRule | None:
        result = await self._db_session.execute(
            select(ClientRule).where(
                ClientRule.client_id == client_id,
                ClientRule.department_id == department_id,
                ClientRule.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_active_by_department(self, department_id: UUID) -> list[ClientRule]:
        result = await self._db_session.execute(
            select(ClientRule).where(
                ClientRule.department_id == department_id,
                ClientRule.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    async def update(
        self,
        rule: ClientRule,
        *,
        client_id: UUID,
        department_id: UUID,
        weekly_ot_threshold: Decimal,
        weekly_dt_threshold: Decimal | None,
        ot_multiplier: Decimal,
        dt_multiplier: Decimal,
        break_deduction_hrs: Decimal | None,
        break_auto_deduct: bool,
    ) -> ClientRule:
        try:
            rule.client_id = client_id
            rule.department_id = department_id
            rule.weekly_ot_threshold = weekly_ot_threshold
            rule.weekly_dt_threshold = weekly_dt_threshold
            rule.ot_multiplier = ot_multiplier
            rule.dt_multiplier = dt_multiplier
            rule.break_deduction_hrs = break_deduction_hrs
            rule.break_auto_deduct = break_auto_deduct
            await self._db_session.flush()
            return rule
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to update client rule") from err

    async def soft_delete(self, rule: ClientRule) -> None:
        try:
            rule.is_active = False
            await self._db_session.flush()
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to delete client rule") from err
