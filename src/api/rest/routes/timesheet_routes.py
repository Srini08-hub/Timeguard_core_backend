import uuid

from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_timesheet_service
from src.core.services.timesheet_service import TimesheetService
from src.schemas.timesheet_schema import TimesheetResponse

router = APIRouter(prefix="/timesheet", tags=["timesheet"])


@router.get(
    "/under_review",
    response_model=list[TimesheetResponse],
    status_code=status.HTTP_200_OK,
)
async def get_under_review_timesheets(
    timesheet_service: TimesheetService = Depends(get_timesheet_service),
) -> list[TimesheetResponse]:
    return await timesheet_service.get_under_review_timesheets()


@router.get(
    "/processed",
    response_model=list[TimesheetResponse],
    status_code=status.HTTP_200_OK,
)
async def get_processed_timesheets(
    timesheet_service: TimesheetService = Depends(get_timesheet_service),
) -> list[TimesheetResponse]:
    return await timesheet_service.get_processed_timesheets()


@router.patch(
    "/{timesheet_id}/processed",
    response_model=TimesheetResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_timesheet_processed(
    timesheet_id: uuid.UUID = Path(..., description="Timesheet ID"),
    timesheet_service: TimesheetService = Depends(get_timesheet_service),
) -> TimesheetResponse:
    return await timesheet_service.mark_processed(timesheet_id)
