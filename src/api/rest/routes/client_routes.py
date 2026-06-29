import uuid

from fastapi import APIRouter, Depends, status

from src.api.rest.dependency.services import get_client_service
from src.core.services.client_service import ClientService
from src.schemas.client_schema import ClientCreate, ClientResponse, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post(
    "",
    response_model=ClientResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_client(
    payload: ClientCreate,
    client_service: ClientService = Depends(get_client_service),
) -> ClientResponse:

    return await client_service.create_client(payload)


@router.get(
    "",
    response_model=list[ClientResponse],
    status_code=status.HTTP_200_OK,
)
async def get_active_clients(
    client_service: ClientService = Depends(get_client_service),
) -> list[ClientResponse]:
    return await client_service.get_active_clients()


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    status_code=status.HTTP_200_OK,
)
async def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    client_service: ClientService = Depends(get_client_service),
) -> ClientResponse:
    return await client_service.update_client(client_id, payload)


@router.delete(
    "/{client_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def soft_delete_client(
    client_id: uuid.UUID,
    client_service: ClientService = Depends(get_client_service),
) -> None:
    await client_service.soft_delete_client(client_id)
