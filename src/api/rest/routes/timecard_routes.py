import uuid

from fastapi import APIRouter, Depends, Path, status

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
