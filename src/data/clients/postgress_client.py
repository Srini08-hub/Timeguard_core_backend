from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.config.settings import settings

database_uri = settings.DATABASE_URI
engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker | None = None


def init_async_engine() -> AsyncEngine:
    global engine, SessionLocal
    if engine is None:
        engine = create_async_engine(
            database_uri,
            pool_size=10,
            max_overflow=10,
            pool_timeout=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={
                "timeout": 180,
                "command_timeout": 2400,
                "server_settings": {"statement_timeout": "2400000"},
            },
        )
        SessionLocal = async_sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return engine


async def dispose_async_engine() -> None:
    global engine, SessionLocal
    if engine is not None:
        await engine.dispose()
        engine = None
        SessionLocal = None
