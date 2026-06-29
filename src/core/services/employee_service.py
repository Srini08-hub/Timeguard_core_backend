from uuid import UUID

from src.core.exceptions.custom_exception import (
    ConflictException,
    DatabaseException,
    ResourceNotFound,
)
from src.data.models.assignments import AssignmentStatus
from src.data.models.employee import Employee
from src.data.repositories.assignment_repository import AssignmentRepository
from src.data.repositories.employee_repository import EmployeeRepository
from src.schemas.employee_schema import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
)


class EmployeeService:
    def __init__(
        self,
        employee_repository: EmployeeRepository,
        assignment_repository: AssignmentRepository,
    ) -> None:
        self._employee_repository = employee_repository
        self._assignment_repository = assignment_repository

    async def create_employee(self, payload: EmployeeCreate) -> EmployeeResponse:
        existing_employee = await self._employee_repository.get_by_email(payload.email)
        if existing_employee is not None:
            raise ConflictException("Employee with this email already exists")
        try:
            employee = await self._employee_repository.create(
                name=payload.name,
                email=payload.email,
                created_by=payload.created_by,
            )
        except Exception as exc:
            raise DatabaseException("Failed to create employee") from exc

        return self._to_response(employee)

    async def get_inactive_employees(self) -> list[EmployeeResponse]:
        employees = await self._employee_repository.get_inactive_employees()
        return [self._to_response(employee) for employee in employees]

    async def get_active_employees(self) -> list[EmployeeResponse]:
        employees = await self._employee_repository.get_active_employees()
        return [self._to_response(employee) for employee in employees]

    async def get_unassigned_employees(self) -> list[EmployeeResponse]:
        employees = await self._employee_repository.get_unassigned_employees()
        return [self._to_response(employee) for employee in employees]

    async def get_employee_by_id(self, emp_id: UUID) -> EmployeeResponse:
        employee = await self._employee_repository.get_by_id(emp_id)
        if employee is None:
            raise ResourceNotFound("Employee not found")
        return self._to_response(employee)

    async def update_employee(
        self,
        emp_id: UUID,
        payload: EmployeeUpdate,
    ) -> EmployeeResponse:
        employee = await self._employee_repository.get_by_id(emp_id)
        if employee is None:
            raise ResourceNotFound("Employee not found")
        try:
            updated_employee = await self._employee_repository.update(
                employee,
                name=payload.name,
                email=payload.email,
            )
        except Exception as exc:
            raise DatabaseException("Failed to update employee") from exc

        return self._to_response(updated_employee)

    async def soft_delete_employee(self, emp_id: UUID) -> EmployeeResponse:
        employee = await self._employee_repository.get_by_id(emp_id)
        if employee is None:
            raise ResourceNotFound("Employee not found")
        try:
            # Get all assignments for this employee
            assignments = await self._assignment_repository.get_by_employee(emp_id)

            # Update all assignment statuses to inactive
            for assignment in assignments:
                await self._assignment_repository.update(
                    assignment, status=AssignmentStatus.INACTIVE
                )

            # Soft delete the employee
            deleted_employee = await self._employee_repository.soft_delete(employee)
        except Exception as exc:
            raise DatabaseException("Failed to delete employee") from exc

        return self._to_response(deleted_employee)

    def _to_response(self, employee: Employee) -> EmployeeResponse:
        return EmployeeResponse(
            emp_id=employee.emp_id,
            email=employee.email,
            name=employee.name,
            is_active=employee.is_active,
            is_assigned=employee.is_assigned,
            created_at=employee.created_at,
        )
