from uuid import UUID

from src.core.exceptions.custom_exception import (
    ConflictException,
    DatabaseException,
    ResourceNotFound,
)
from src.data.models.assignments import AssignmentStatus
from src.data.models.department import Department
from src.data.repositories.assignment_repository import AssignmentRepository
from src.data.repositories.department_repository import DepartmentRepository
from src.data.repositories.employee_repository import EmployeeRepository
from src.schemas.department_schema import (
    DepartmentCreate,
    DepartmentResponse,
    DepartmentUpdate,
)


class DepartmentService:
    def __init__(
        self,
        department_repository: DepartmentRepository,
        assignment_repository: AssignmentRepository,
        employee_repository: EmployeeRepository,
    ) -> None:
        self._department_repository = department_repository
        self._assignment_repository = assignment_repository
        self._employee_repository = employee_repository

    async def create_department(self, payload: DepartmentCreate) -> DepartmentResponse:
        existing_department = await self._department_repository.get_by_name_and_client(
            payload.department_name, payload.client_id
        )
        if existing_department is not None:
            raise ConflictException("Department with this name already exists for this client")

        try:
            department = await self._department_repository.create(
                client_id=payload.client_id, department_name=payload.department_name
            )
            return self._to_response(department)
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to create department") from exc

    async def get_department(self, department_id: UUID) -> DepartmentResponse:
        department = await self._department_repository.get_by_id(department_id)
        if department is None:
            raise ResourceNotFound("Department not found")
        return self._to_response(department)

    async def get_departments_by_client(self, client_id: UUID) -> list[DepartmentResponse]:
        departments = await self._department_repository.get_by_client(client_id)
        return [self._to_response(dept) for dept in departments]

    async def update_department(
        self, department_id: UUID, payload: DepartmentUpdate
    ) -> DepartmentResponse:
        department = await self._department_repository.get_by_id(department_id)
        if department is None:
            raise ResourceNotFound("Department not found")

        # if payload.department_name:
        #     existing_department = await self._department_repository
        #  .get_by_name_and_client(
        #         payload.department_name, department.client_id
        #     )
        #     if existing_department is not None and existing_department.
        # department_id != department_id:
        #         raise ConflictException("Department with this name
        #  already exists for this client")

        try:
            updated_department = await self._department_repository.update(
                department,
                department_name=payload.department_name or department.department_name,
            )
            return self._to_response(updated_department)
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to update department") from exc

    async def delete_department(self, department_id: UUID) -> None:
        department = await self._department_repository.get_by_id(department_id)
        if department is None:
            raise ResourceNotFound("Department not found")

        try:
            # Get all assignments for this department
            assignments = await self._assignment_repository.get_by_department(department_id)

            # Update assignment status to inactive
            await self._assignment_repository.update_by_department(
                department_id, status=AssignmentStatus.INACTIVE
            )

            # Update employees is_assigned to false
            for assignment in assignments:
                await self._employee_repository.update_assignment(assignment.emp_id, False)

            # Soft delete the department
            await self._department_repository.delete(department)

        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to delete department") from exc

    def _to_response(self, department: Department) -> DepartmentResponse:
        return DepartmentResponse(
            department_id=department.department_id,
            client_id=department.client_id,
            department_name=department.department_name,
            created_at=department.created_at,
        )
