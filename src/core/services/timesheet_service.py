from src.data.repositories.timesheet_repository import TimesheetRepository
from src.schemas.timesheet_schema import TimesheetResponse


class TimesheetService:
    def __init__(self, timesheet_repo: TimesheetRepository):
        self.timesheet_repo = timesheet_repo

    async def get_pending_timesheets(self) -> list[TimesheetResponse]:
        timesheets = await self.timesheet_repo.get_pending_timesheets()
        return [
            TimesheetResponse(
                timesheet_id=timesheet.timesheet_id,
                email_id=timesheet.email_id,
                attachment_id=timesheet.attachment_id,
                source_type=timesheet.source_type,
                client_name=timesheet.client_name,
                week_ending=timesheet.week_ending,
                extracted_payload=timesheet.extracted_payload,
                status=timesheet.status,
                created_at=timesheet.created_at,
            )
            for timesheet in timesheets
        ]
