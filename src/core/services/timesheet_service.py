from uuid import UUID

from src.core.exceptions.custom_exception import ResourceNotFound
from src.data.models.timesheet import Timesheet, TimesheetStatus
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.schemas.timesheet_schema import TimesheetResponse


class TimesheetService:
    def __init__(self, timesheet_repo: TimesheetRepository) -> None:
        self.timesheet_repo = timesheet_repo

    def _to_response(self, timesheet: Timesheet) -> TimesheetResponse:
        return TimesheetResponse(
            timesheet_id=timesheet.timesheet_id,
            email_id=timesheet.email_id,
            client_name=timesheet.client_name,
            week_ending=timesheet.week_ending,
            payload=timesheet.payload,
            status=timesheet.status,
            created_at=timesheet.created_at,
        )

    async def get_under_review_timesheets(self) -> list[TimesheetResponse]:
        timesheets = await self.timesheet_repo.get_under_review_timesheets()
        return [self._to_response(timesheet) for timesheet in timesheets]

    async def get_processed_timesheets(self) -> list[TimesheetResponse]:
        timesheets = await self.timesheet_repo.get_processed_timesheets()
        return [self._to_response(timesheet) for timesheet in timesheets]

    async def mark_processed(self, timesheet_id: UUID) -> TimesheetResponse:
        timesheet = await self.timesheet_repo.set_status(
            timesheet_id=timesheet_id,
            status=TimesheetStatus.PROCESSED,
        )
        if timesheet is None:
            raise ResourceNotFound("Timesheet not found")
        return self._to_response(timesheet)
