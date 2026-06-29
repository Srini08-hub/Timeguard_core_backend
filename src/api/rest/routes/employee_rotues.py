from uuid import UUID

from fastapi import APIRouter, Depends, Path, status

from src.api.rest.dependency.services import get_employee_service
from src.core.services.employee_service import EmployeeService
from src.schemas.employee_schema import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)

router = APIRouter(prefix="/employees", tags=["employees"])


@router.post(
    "",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    payload: EmployeeCreate,
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await employee_service.create_employee(payload)


@router.get(
    "/active",
    response_model=list[EmployeeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_active_employees(
    employee_service: EmployeeService = Depends(get_employee_service),
) -> list[EmployeeResponse]:
    return await employee_service.get_active_employees()


@router.get(
    "/inactive",
    response_model=list[EmployeeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_inactive_employees(
    employee_service: EmployeeService = Depends(get_employee_service),
) -> list[EmployeeResponse]:
    return await employee_service.get_inactive_employees()


@router.get(
    "/unassigned",
    response_model=list[EmployeeResponse],
    status_code=status.HTTP_200_OK,
)
async def get_unassigned_employees(
    employee_service: EmployeeService = Depends(get_employee_service),
) -> list[EmployeeResponse]:
    return await employee_service.get_unassigned_employees()


@router.get(
    "/{emp_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_employee(
    emp_id: UUID = Path(description="The employee ID to fetch"),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await employee_service.get_employee_by_id(emp_id)


@router.put(
    "/{emp_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
)
async def update_employee(
    payload: EmployeeUpdate,
    emp_id: UUID = Path(description="The employee ID to update"),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await employee_service.update_employee(emp_id, payload)


@router.delete(
    "/{emp_id}",
    response_model=EmployeeResponse,
    status_code=status.HTTP_200_OK,
)
async def soft_delete_employee(
    emp_id: UUID = Path(description="The employee ID to delete"),
    employee_service: EmployeeService = Depends(get_employee_service),
) -> EmployeeResponse:
    return await employee_service.soft_delete_employee(emp_id)
