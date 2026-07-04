from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions.custom_exception import DatabaseException
from src.data.models.assignments import Assignment
from src.data.models.client_rules import ClientRule
from src.data.models.timecard import ExceptionSeverity as TimecardSeverity
from src.data.models.timecard import Timecard, TimecardStatus


class TimecardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_timesheet(self, timesheet_id: UUID) -> list[Timecard]:
        try:
            result = await self._session.execute(
                select(Timecard)
                .options(selectinload(Timecard.exceptions))
                .where(Timecard.timesheet_id == timesheet_id)
                .order_by(Timecard.employee_name.asc(), Timecard.created_at.asc())
            )
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to get timecards by timesheet: {str(e)}") from e

    async def get_by_status(
        self,
        status: TimecardStatus,
        *,
        week_ending: date | None = None,
    ) -> list[Timecard]:
        try:
            statement = (
                select(Timecard)
                .options(selectinload(Timecard.exceptions))
                .where(Timecard.status == status)
            )
            if week_ending is not None:
                statement = statement.where(Timecard.week_ending == week_ending)
            statement = statement.order_by(
                Timecard.week_ending.desc(),
                Timecard.employee_name.asc(),
                Timecard.created_at.asc(),
            )
            result = await self._session.execute(statement)
            return list(result.scalars().all())
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to get timecards by status: {str(e)}") from e

    async def get_by_id(self, timecard_id: UUID) -> Timecard | None:
        try:
            result = await self._session.execute(
                select(Timecard)
                .options(selectinload(Timecard.exceptions))
                .where(Timecard.timecard_id == timecard_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to get timecard by id: {str(e)}") from e

    async def get_assignment(self, assignment_id: UUID) -> Assignment | None:
        try:
            result = await self._session.execute(
                select(Assignment).where(Assignment.assignment_id == assignment_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to get assignment for timecard: {str(e)}") from e

    async def get_client_rule(self, rule_id: UUID) -> ClientRule | None:
        try:
            result = await self._session.execute(
                select(ClientRule).where(ClientRule.rule_id == rule_id)
            )
            return result.scalar_one_or_none()
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to get client rule for timecard: {str(e)}") from e

    # async def delete_by_timesheet(self, timesheet_id: UUID) -> None:
    #     await self._session.execute(
    #         delete(Timecard).where(Timecard.timesheet_id == timesheet_id)
    #     )
    #     await self._session.flush()

    async def create_generated_timecard(
        self,
        *,
        timesheet_id: UUID,
        emp_id: UUID | None,
        assignment_id: UUID | None,
        rule_id: UUID | None,
        week_ending: date,
        employee_name: str | None,
        reg_hours: Decimal | None,
        ot_hours: Decimal | None,
        dt_hours: Decimal | None,
        status: TimecardStatus,
        severity: TimecardSeverity,
    ) -> Timecard:
        try:
            timecard = Timecard(
                timesheet_id=timesheet_id,
                emp_id=emp_id,
                assignment_id=assignment_id,
                rule_id=rule_id,
                week_ending=week_ending,
                employee_name=employee_name,
                reg_hours=reg_hours,
                ot_hours=ot_hours,
                dt_hours=dt_hours,
                status=status,
                severity=severity,
            )
            self._session.add(timecard)
            await self._session.flush()
            await self._session.refresh(timecard)
            return timecard
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to create timecard: {str(e)}") from e

    async def set_status(
        self,
        timecard: Timecard,
        status: TimecardStatus,
    ) -> Timecard:
        try:
            timecard.status = status
            if status == TimecardStatus.NO_EXCEPTION:
                timecard.severity = TimecardSeverity.NONE
            await self._session.flush()
            await self._session.refresh(timecard)
            return timecard
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to set timecard status: {str(e)}") from e

    async def set_approved_payroll(
        self,
        timecard: Timecard,
        *,
        pay_rate: Decimal,
        regular_pay: Decimal,
        ot_pay: Decimal,
        dt_pay: Decimal,
        gross_pay: Decimal,
    ) -> Timecard:
        try:
            timecard.pay_rate = pay_rate
            timecard.regular_pay = regular_pay
            timecard.ot_pay = ot_pay
            timecard.dt_pay = dt_pay
            timecard.gross_pay = gross_pay
            timecard.status = TimecardStatus.APPROVED
            await self._session.flush()
            await self._session.refresh(timecard)
            return timecard
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to approve timecard payroll: {str(e)}") from e

    async def resolve_with_update(
        self,
        timecard: Timecard,
        *,
        employee_name: str | None = None,
        reg_hours: Decimal | None = None,
        ot_hours: Decimal | None = None,
        dt_hours: Decimal | None = None,
        review_comment: str | None = None,
        reviewed_by: UUID | None = None,
    ) -> Timecard:
        try:
            if employee_name is not None:
                timecard.employee_name = employee_name
            if reg_hours is not None:
                timecard.reg_hours = reg_hours
            if ot_hours is not None:
                timecard.ot_hours = ot_hours
            if dt_hours is not None:
                timecard.dt_hours = dt_hours
            if review_comment is not None:
                timecard.review_comment = review_comment
            if reviewed_by is not None:
                timecard.reviewed_by = reviewed_by

            timecard.status = TimecardStatus.NO_EXCEPTION
            timecard.severity = TimecardSeverity.NONE
            await self._session.flush()
            await self._session.refresh(timecard)
            return timecard
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to resolve timecard: {str(e)}") from e

    async def approve_many(self, timecard_ids: list[UUID]) -> list[Timecard]:
        try:
            timecards: list[Timecard] = []
            for timecard_id in timecard_ids:
                timecard = await self.get_by_id(timecard_id)
                if timecard is None:
                    continue
                timecard.status = TimecardStatus.APPROVED
                timecards.append(timecard)
            await self._session.flush()
            for timecard in timecards:
                await self._session.refresh(timecard)
            return timecards
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to approve timecards: {str(e)}") from e

    async def reject(self, timecard: Timecard) -> Timecard:
        try:
            timecard.status = TimecardStatus.REJECTED
            await self._session.flush()
            await self._session.refresh(timecard)
            return timecard
        except SQLAlchemyError as e:
            raise DatabaseException(f"Failed to reject timecard: {str(e)}") from e
