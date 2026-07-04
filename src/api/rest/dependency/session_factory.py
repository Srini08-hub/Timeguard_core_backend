from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.data.clients import postgress_client


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if postgress_client.SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database session factory is not initialized",
        )

    return postgress_client.SessionLocal
