import logging
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.timesheet import Timesheet, TimesheetStatus

logger = logging.getLogger(__name__)


class TimesheetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_under_review_timesheets(self) -> list[Timesheet]:
        result = await self._session.execute(
            select(Timesheet)
            .where(Timesheet.status == TimesheetStatus.UNDER_REVIEW)
            .order_by(Timesheet.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_processed_timesheets(self) -> list[Timesheet]:
        result = await self._session.execute(
            select(Timesheet)
            .where(Timesheet.status == TimesheetStatus.PROCESSED)
            .order_by(Timesheet.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, *, timesheet_id: UUID) -> Timesheet | None:
        result = await self._session.execute(
            select(Timesheet).where(Timesheet.timesheet_id == timesheet_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email_id(self, *, email_id: UUID) -> Timesheet | None:
        result = await self._session.execute(
            select(Timesheet).where(Timesheet.email_id == email_id)
        )
        return result.scalar_one_or_none()

    async def set_status(
        self,
        *,
        timesheet_id: UUID,
        status: TimesheetStatus,
    ) -> Timesheet | None:
        timesheet = await self.get_by_id(timesheet_id=timesheet_id)
        if timesheet is None:
            logger.warning(
                "Timesheet not found for timesheet_id %s when updating status",
                timesheet_id,
            )
            return None

        timesheet.status = status
        await self._session.flush()
        logger.info("Updated timesheet %s status to %s", timesheet_id, status)
        return timesheet

    async def update_timesheet(
        self,
        *,
        email_id: UUID,
        client_name: str | None = None,
        week_ending: date | None = None,
        payload: Any = None,
        status: TimesheetStatus | None = None,
    ) -> Timesheet | None:
        timesheet = await self.get_by_email_id(email_id=email_id)
        if timesheet is None:
            logger.warning(
                "Timesheet not found for email_id %s when updating",
                email_id,
            )
            return None

        if client_name is not None:
            timesheet.client_name = client_name

        if week_ending is not None:
            timesheet.week_ending = week_ending

        if payload is not None:
            timesheet.payload = payload

        if status is not None:
            timesheet.status = status

        await self._session.flush()
        logger.info("Updated timesheet for email_id %s", email_id)
        return timesheet

    async def create_with_merge_data(
        self,
        *,
        email_id: UUID,
        client_name: str | None = None,
        week_ending: date | None = None,
        payload: Any = None,
    ) -> Timesheet:

        timesheet = Timesheet(
            email_id=email_id,
            client_name=client_name,
            week_ending=week_ending,
            payload=payload,
            status=TimesheetStatus.PENDING,
        )
        self._session.add(timesheet)
        await self._session.flush()
        logger.info(
            "Created Timesheet record %s for email_id=%s with client_name=%s week_ending=%s",
            timesheet.timesheet_id,
            email_id,
            client_name,
            week_ending,
        )
        return timesheet
