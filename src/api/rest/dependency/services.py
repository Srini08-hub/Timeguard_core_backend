from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependency.session import get_async_db
from src.core.services.email_service import EmailService
from src.core.services.timesheet_service import TimesheetService
from src.data.repositories.email_repository import EmailRepository
from src.data.repositories.timesheet_repository import TimesheetRepository


async def get_email_service(
    db: AsyncSession = Depends(get_async_db),
) -> EmailService:
    return EmailService(EmailRepository(db))


async def get_timesheet_service(
    db: AsyncSession = Depends(get_async_db),
) -> TimesheetService:
    return TimesheetService(TimesheetRepository(db))
