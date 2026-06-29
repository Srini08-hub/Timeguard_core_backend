import uuid

from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_assignment_service
from src.core.services.assignment_service import AssignmentService
from src.schemas.assignment_schema import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post(
    "",
    response_model=list[AssignmentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    payload: list[AssignmentCreate],
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> list[AssignmentResponse]:
    return await assignment_service.create_assignment(payload)


@router.get(
    "/employee/{emp_id}",
    response_model=list[AssignmentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_assignments_by_employee(
    emp_id: uuid.UUID,
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> list[AssignmentResponse]:
    return await assignment_service.get_assignments_by_employee(emp_id)


@router.get(
    "/client/{client_id}",
    response_model=list[AssignmentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_assignments_by_client(
    client_id: uuid.UUID,
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> list[AssignmentResponse]:
    return await assignment_service.get_assignments_by_client(client_id)


@router.get(
    "/department/{department_id}",
    response_model=list[AssignmentResponse],
    status_code=status.HTTP_200_OK,
)
async def get_assignments_by_department(
    department_id: uuid.UUID,
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> list[AssignmentResponse]:
    return await assignment_service.get_assignments_by_department(department_id)


@router.get(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_200_OK,
)
async def get_assignment(
    assignment_id: uuid.UUID = Path(..., description="Assignment ID"),
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> AssignmentResponse:
    return await assignment_service.get_assignment(assignment_id)


@router.patch(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    status_code=status.HTTP_200_OK,
)
async def update_assignment(
    payload: AssignmentUpdate,
    assignment_id: uuid.UUID = Path(..., description="Assignment ID"),
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> AssignmentResponse:
    return await assignment_service.update_assignment(assignment_id, payload)


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_assignment(
    assignment_id: uuid.UUID = Path(..., description="Assignment ID"),
    assignment_service: AssignmentService = Depends(get_assignment_service),
) -> None:
    await assignment_service.delete_assignment(assignment_id)
