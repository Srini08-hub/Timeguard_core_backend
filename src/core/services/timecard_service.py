from uuid import UUID

from src.core.exceptions.custom_exception import ResourceNotFound
from src.data.models.timecard import Timecard, TimecardStatus
from src.data.repositories.exception_repository import ExceptionRepository
from src.data.repositories.timecard_repository import TimecardRepository
from src.schemas.timecard_schema import TimecardResponse, TimecardUpdate


class TimecardService:
    def __init__(
        self,
        timecard_repository: TimecardRepository,
        exception_repository: ExceptionRepository,
    ) -> None:
        self._timecard_repository = timecard_repository
        self._exception_repository = exception_repository

    async def get_timecards_by_timesheet(
        self,
        timesheet_id: UUID,
    ) -> list[TimecardResponse]:
        timecards = await self._timecard_repository.get_by_timesheet(timesheet_id)
        return [self._to_response(timecard) for timecard in timecards]

    async def get_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        return self._to_response(timecard)

    async def approve_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        updated = await self._timecard_repository.set_status(
            timecard,
            TimecardStatus.APPROVED,
        )
        return self._to_response(updated)

    async def approve_timecards(
        self,
        timecard_ids: list[UUID],
    ) -> list[TimecardResponse]:
        timecards = await self._timecard_repository.approve_many(timecard_ids)
        return [self._to_response(timecard) for timecard in timecards]

    async def reject_timecard(self, timecard_id: UUID) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        updated = await self._timecard_repository.reject(timecard)
        return self._to_response(updated)

    async def resolve_timecard(
        self,
        timecard_id: UUID,
        payload: TimecardUpdate,
    ) -> TimecardResponse:
        timecard = await self._timecard_repository.get_by_id(timecard_id)
        if timecard is None:
            raise ResourceNotFound("Timecard not found")
        updated = await self._timecard_repository.resolve_with_update(
            timecard,
            employee_name=payload.employee_name,
            reg_hours=payload.reg_hours,
            ot_hours=payload.ot_hours,
            dt_hours=payload.dt_hours,
            review_comment=payload.review_comment,
            reviewed_by=payload.reviewed_by,
        )
        await self._exception_repository.resolve_exceptions(updated.exceptions)
        return self._to_response(updated)

    def _to_response(self, timecard: Timecard) -> TimecardResponse:
        return TimecardResponse.model_validate(timecard)
