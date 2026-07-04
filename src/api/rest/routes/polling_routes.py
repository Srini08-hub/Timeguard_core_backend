from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.api.rest.dependency.session_factory import get_session_factory
from src.core.services.gmail_polling_controller import gmail_polling_controller
from src.schemas.polling_schema import PollingStartRequest, PollingStatusResponse

router = APIRouter(prefix="/polling", tags=["polling"])


@router.get(
    "/status",
    response_model=PollingStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_polling_status() -> PollingStatusResponse:
    return PollingStatusResponse(**gmail_polling_controller.status())


@router.post(
    "/start",
    response_model=PollingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_polling(
    payload: PollingStartRequest,
    session_factory: Annotated[
        async_sessionmaker[AsyncSession],
        Depends(get_session_factory),
    ],
) -> PollingStatusResponse:
    await gmail_polling_controller.start(session_factory, payload.interval_seconds)
    return PollingStatusResponse(**gmail_polling_controller.status())


@router.post(
    "/stop",
    response_model=PollingStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_polling() -> PollingStatusResponse:
    await gmail_polling_controller.stop()
    return PollingStatusResponse(**gmail_polling_controller.status())
