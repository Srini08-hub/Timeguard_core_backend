from fastapi import APIRouter, Depends, status

from src.api.rest.dependency.services import get_timesheet_service
from src.core.services.timesheet_service import TimesheetService
from src.schemas.timesheet_schema import TimesheetResponse

router = APIRouter(prefix="/timesheet", tags=["timesheet"])


@router.get(
    "/pending",
    response_model=list[TimesheetResponse],
    status_code=status.HTTP_200_OK,
)
async def get_pending_timesheets(
    timesheet_service: TimesheetService = Depends(get_timesheet_service),
) -> list[TimesheetResponse]:
    return await timesheet_service.get_pending_timesheets()
