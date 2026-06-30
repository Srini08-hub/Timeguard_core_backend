import uuid
from datetime import date

from fastapi import APIRouter, Depends, Path, Query, Response, status

from src.api.rest.dependency.services import get_timecard_service
from src.core.services.timecard_service import TimecardService
from src.schemas.timecard_schema import (
    TimecardBulkAction,
    TimecardResponse,
    TimecardUpdate,
)

router = APIRouter(prefix="/timecards", tags=["timecards"])


@router.get(
    "/timesheet/{timesheet_id}",
    response_model=list[TimecardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_timecards_by_timesheet(
    timesheet_id: uuid.UUID = Path(..., description="Timesheet ID"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> list[TimecardResponse]:
    return await timecard_service.get_timecards_by_timesheet(timesheet_id)


@router.get(
    "/approved/export",
    status_code=status.HTTP_200_OK,
)
async def export_approved_timecards(
    week_ending: date = Query(..., description="Week ending date"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> Response:
    content = await timecard_service.export_approved_timecards(week_ending)
    filename = f"approved-timecards-{week_ending}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/approved",
    response_model=list[TimecardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_approved_timecards(
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> list[TimecardResponse]:
    return await timecard_service.get_approved_timecards()


@router.get(
    "/rejected",
    response_model=list[TimecardResponse],
    status_code=status.HTTP_200_OK,
)
async def get_rejected_timecards(
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> list[TimecardResponse]:
    return await timecard_service.get_rejected_timecards()


@router.patch(
    "/bulk/approve",
    response_model=list[TimecardResponse],
    status_code=status.HTTP_200_OK,
)
async def approve_timecards(
    payload: TimecardBulkAction,
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> list[TimecardResponse]:
    return await timecard_service.approve_timecards(payload.timecard_ids)


@router.get(
    "/{timecard_id}",
    response_model=TimecardResponse,
    status_code=status.HTTP_200_OK,
)
async def get_timecard(
    timecard_id: uuid.UUID = Path(..., description="Timecard ID"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> TimecardResponse:
    return await timecard_service.get_timecard(timecard_id)


@router.patch(
    "/{timecard_id}/resolve",
    response_model=TimecardResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_timecard(
    payload: TimecardUpdate,
    timecard_id: uuid.UUID = Path(..., description="Timecard ID"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> TimecardResponse:
    return await timecard_service.resolve_timecard(timecard_id, payload)


@router.patch(
    "/{timecard_id}/approve",
    response_model=TimecardResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_timecard(
    timecard_id: uuid.UUID = Path(..., description="Timecard ID"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> TimecardResponse:
    return await timecard_service.approve_timecard(timecard_id)


@router.patch(
    "/{timecard_id}/reject",
    response_model=TimecardResponse,
    status_code=status.HTTP_200_OK,
)
async def reject_timecard(
    timecard_id: uuid.UUID = Path(..., description="Timecard ID"),
    timecard_service: TimecardService = Depends(get_timecard_service),
) -> TimecardResponse:
    return await timecard_service.reject_timecard(timecard_id)
