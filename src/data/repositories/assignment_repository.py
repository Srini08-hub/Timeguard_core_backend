import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.custom_exception import (
    DatabaseException,
)
from src.data.models.assignments import Assignment, AssignmentStatus

logger = logging.getLogger(__name__)


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, emp_id: UUID, client_id: UUID, department_id: UUID) -> Assignment:
        try:
            assignment = Assignment(
                emp_id=emp_id, client_id=client_id, department_id=department_id
            )
            self._session.add(assignment)

            await self._session.flush()
            return assignment
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to create assignment") from err

    async def get_by_id(self, assignment_id: UUID) -> Assignment | None:
        result = await self._session.execute(
            select(Assignment).where(Assignment.assignment_id == assignment_id)
        )
        return result.scalar_one_or_none()

    async def get_by_employee(self, emp_id: UUID) -> list[Assignment]:
        result = await self._session.execute(
            select(Assignment).where(Assignment.emp_id == emp_id)
        )
        return list(result.scalars().all())

    async def get_active_by_employee(self, emp_id: UUID) -> Assignment | None:
        result = await self._session.execute(
            select(Assignment).where(
                Assignment.emp_id == emp_id, Assignment.status == AssignmentStatus.ACTIVE
            )
        )
        return result.scalar_one_or_none()

    async def get_by_client(self, client_id: UUID) -> list[Assignment]:
        result = await self._session.execute(
            select(Assignment).where(Assignment.client_id == client_id)
        )
        return list(result.scalars().all())

    async def update_by_client(
        self, client_id: UUID, *, status: AssignmentStatus
    ) -> list[Assignment]:
        try:
            result = await self._session.execute(
                select(Assignment).where(Assignment.client_id == client_id)
            )
            assignments = list(result.scalars().all())
            for assignment in assignments:
                assignment.status = status
            await self._session.flush()
            return assignments
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to update assignments by client") from err

    async def get_by_department(self, department_id: UUID) -> list[Assignment]:
        result = await self._session.execute(
            select(Assignment).where(
                Assignment.department_id == department_id,
                Assignment.status == AssignmentStatus.ACTIVE,
            )
        )
        return list(result.scalars().all())

    async def update_by_department(
        self, department_id: UUID, *, status: AssignmentStatus
    ) -> list[Assignment]:
        try:
            result = await self._session.execute(
                select(Assignment).where(Assignment.department_id == department_id)
            )
            assignments = list(result.scalars().all())
            for assignment in assignments:
                assignment.status = status
            await self._session.flush()
            return assignments
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to update assignments by department") from err

    async def update(self, assignment: Assignment, *, status: AssignmentStatus) -> Assignment:
        try:
            assignment.status = status
            await self._session.flush()
            return assignment
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to update assignment") from err

    async def delete(self, assignment: Assignment) -> None:
        try:
            assignment.status = AssignmentStatus.INACTIVE
            await self._session.flush()
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to delete assignment") from err
