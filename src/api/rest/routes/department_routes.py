import uuid

from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_department_service
from src.core.services.department_service import DepartmentService
from src.schemas.department_schema import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)

router = APIRouter(prefix="/departments", tags=["departments"])


@router.post(
    "",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_department(
    payload: DepartmentCreate,
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await department_service.create_department(payload)


@router.get(
    "/client/{client_id}",
    response_model=list[DepartmentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_departments_by_client(
    client_id: uuid.UUID,
    department_service: DepartmentService = Depends(get_department_service),
) -> list[DepartmentResponse]:
    return await department_service.get_departments_by_client(client_id)


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_department(
    department_id: uuid.UUID = Path(..., description="Department ID"),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await department_service.get_department(department_id)


@router.patch(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
)
async def update_department(
    payload: DepartmentUpdate,
    department_id: uuid.UUID = Path(..., description="Department ID"),
    department_service: DepartmentService = Depends(get_department_service),
) -> DepartmentResponse:
    return await department_service.update_department(department_id, payload)


@router.delete(
    "/{department_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_department(
    department_id: uuid.UUID = Path(..., description="Department ID"),
    department_service: DepartmentService = Depends(get_department_service),
) -> None:
    await department_service.delete_department(department_id)
