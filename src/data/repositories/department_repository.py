from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions.custom_exception import (
    DatabaseException,
)
from src.data.models.department import Department


class DepartmentRepository:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create(self, client_id: UUID, department_name: str) -> Department:
        try:
            department = Department(client_id=client_id, department_name=department_name)
            self._db_session.add(department)
            await self._db_session.flush()
            return department
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to create department") from err

    async def get_by_id(self, department_id: UUID) -> Department | None:
        result = await self._db_session.execute(
            select(Department).where(Department.department_id == department_id)
        )
        return result.scalar_one_or_none()

    async def get_by_client(self, client_id: UUID) -> list[Department]:
        result = await self._db_session.execute(
            select(Department)
            .where(Department.client_id == client_id)
            .where(Department.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_all_by_client(self, client_id: UUID) -> list[Department]:
        result = await self._db_session.execute(
            select(Department).where(Department.client_id == client_id)
        )
        return list(result.scalars().all())

    async def soft_delete_by_client(self, client_id: UUID) -> list[Department]:
        try:
            result = await self._db_session.execute(
                select(Department).where(Department.client_id == client_id)
            )
            departments = list(result.scalars().all())
            for department in departments:
                department.is_active = False
            await self._db_session.flush()
            return departments
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to soft delete departments by client") from err

    async def get_by_name_and_client(
        self, department_name: str, client_id: UUID
    ) -> Department | None:
        result = await self._db_session.execute(
            select(Department).where(
                Department.department_name == department_name,
                Department.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, department: Department, *, department_name: str) -> Department:
        try:
            department.department_name = department_name
            await self._db_session.flush()
            return department
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to update department") from err

    async def delete(self, department: Department) -> None:
        try:
            department.is_active = False
            await self._db_session.flush()
        except SQLAlchemyError as err:
            raise DatabaseException("Failed to delete department") from err
