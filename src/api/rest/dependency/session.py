from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.clients import postgress_client


async def get_async_db() -> AsyncGenerator[AsyncSession]:
    if postgress_client.SessionLocal is not None:
        async with postgress_client.SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
