from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models.employee import Employee
from src.data.models.user import User


class EmployeeRepository:
    def __init__(self, db_session: AsyncSession):
        self._db_session = db_session

    async def create(
        self,
        *,
        name: str,
        email: str,
        created_by: UUID,
    ) -> Employee:
        employee = Employee(name=name, email=email, created_by=created_by)
        self._db_session.add(employee)
        await self._db_session.flush()
        return employee

    async def user_exists(self, user_id: UUID) -> bool:
        result = await self._db_session.execute(
            select(User.user_id).where(User.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def get_by_email(self, email: str) -> Employee | None:
        result = await self._db_session.execute(
            select(Employee).where(Employee.email == email, Employee.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def get_active_employees(self) -> list[Employee]:
        result = await self._db_session.execute(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .order_by(Employee.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_inactive_employees(self) -> list[Employee]:
        result = await self._db_session.execute(
            select(Employee)
            .where(Employee.is_active.is_(False))
            .order_by(Employee.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_unassigned_employees(self) -> list[Employee]:
        result = await self._db_session.execute(
            select(Employee)
            .where(Employee.is_active.is_(True))
            .where(Employee.is_assigned.is_(False))
            .order_by(Employee.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_assignment(self, emp_id: UUID, is_assigned: bool) -> None:
        result = await self._db_session.execute(
            select(Employee).where(
                Employee.emp_id == emp_id,
            )
        )
        employee = result.scalar_one()
        employee.is_assigned = is_assigned
        await self._db_session.flush()

    async def get_by_id(self, emp_id: UUID) -> Employee | None:
        result = await self._db_session.execute(
            select(Employee).where(
                Employee.emp_id == emp_id,
            )
        )
        return result.scalar_one_or_none()

    async def update(
        self, employee: Employee, *, name: str | None = None, email: str | None = None
    ) -> Employee:
        if name is not None:
            employee.name = name
        if email is not None:
            employee.email = email
        await self._db_session.flush()
        return employee

    async def soft_delete(self, employee: Employee) -> Employee:
        employee.is_active = False
        await self._db_session.flush()
        return employee
