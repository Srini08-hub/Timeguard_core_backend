from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.rest.dependency.session import get_async_db
from src.core.services.email_service import EmailService
from src.data.repositories.email_repository import EmailRepository


async def get_email_service(
    db: AsyncSession = Depends(get_async_db),
) -> EmailService:
    return EmailService(EmailRepository(db))
