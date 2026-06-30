from uuid import UUID

from src.core.exceptions.custom_exception import (
    DatabaseException,
    ResourceNotFound,
)
from src.data.models.assignments import Assignment, AssignmentStatus
from src.data.repositories.assignment_repository import AssignmentRepository
from src.data.repositories.employee_repository import EmployeeRepository
from src.schemas.assignment_schema import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)


class AssignmentService:
    def __init__(
        self,
        assignment_repository: AssignmentRepository,
        employee_repository: EmployeeRepository,
    ) -> None:
        self._assignment_repository = assignment_repository
        self._employee_repository = employee_repository

    async def create_assignment(
        self, payload: list[AssignmentCreate]
    ) -> list[AssignmentResponse]:
        # Check if any employee in the payload already has an active assignment
        # for assignment in payload:
        #     existing_active = await self._assignment_repository
        # get_active_by_employee(assignment.emp_id)
        #     if existing_active is not None:
        #         raise ConflictException("Employee already has an active assignment")

        try:
            assignments_list = []
            for assignment_payload in payload:
                assignment = await self._assignment_repository.create(
                    emp_id=assignment_payload.emp_id,
                    client_id=assignment_payload.client_id,
                    department_id=assignment_payload.department_id,
                    pay_rate=assignment_payload.pay_rate,
                )
                await self._employee_repository.update_assignment(
                    assignment.emp_id, is_assigned=True
                )
                assignments_list.append(self._to_response(assignment))

            return assignments_list
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to create assignment") from exc

    async def get_assignment(self, assignment_id: UUID) -> AssignmentResponse:
        assignment = await self._assignment_repository.get_by_id(assignment_id)
        if assignment is None:
            raise ResourceNotFound("Assignment not found")
        return self._to_response(assignment)

    async def get_assignments_by_employee(self, emp_id: UUID) -> list[AssignmentResponse]:
        assignments = await self._assignment_repository.get_by_employee(emp_id)
        return [self._to_response(assignment) for assignment in assignments]

    async def get_assignments_by_client(self, client_id: UUID) -> list[AssignmentResponse]:
        assignments = await self._assignment_repository.get_by_client(client_id)
        return [self._to_response(assignment) for assignment in assignments]

    async def get_assignments_by_department(
        self, department_id: UUID
    ) -> list[AssignmentResponse]:
        assignments = await self._assignment_repository.get_by_department(department_id)
        return [self._to_response(assignment) for assignment in assignments]

    async def update_assignment(
        self, assignment_id: UUID, payload: AssignmentUpdate
    ) -> AssignmentResponse:
        assignment = await self._assignment_repository.get_by_id(assignment_id)
        if assignment is None:
            raise ResourceNotFound("Assignment not found")

        status = AssignmentStatus(payload.status.value) if payload.status else None

        if status is not None or payload.pay_rate is not None:
            try:
                updated_assignment = await self._assignment_repository.update(
                    assignment,
                    status=status,
                    pay_rate=payload.pay_rate,
                )
                return self._to_response(updated_assignment)
            except DatabaseException:
                raise
            except Exception as exc:
                raise DatabaseException("Failed to update assignment") from exc

        return self._to_response(assignment)

    async def delete_assignment(self, assignment_id: UUID) -> None:
        assignment = await self._assignment_repository.get_by_id(assignment_id)
        if assignment is None:
            raise ResourceNotFound("Assignment not found")

        try:
            await self._assignment_repository.delete(assignment)
            await self._employee_repository.update_assignment(
                assignment.emp_id, is_assigned=False
            )
        except DatabaseException:
            raise
        except Exception as exc:
            raise DatabaseException("Failed to delete assignment") from exc

    def _to_response(self, assignment: Assignment) -> AssignmentResponse:
        return AssignmentResponse(
            assignment_id=assignment.assignment_id,
            emp_id=assignment.emp_id,
            client_id=assignment.client_id,
            department_id=assignment.department_id,
            pay_rate=assignment.pay_rate,
            status=assignment.status,
            created_at=assignment.created_at,
        )
