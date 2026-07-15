from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import settings

engine = create_engine(
    settings.SYNC_DATABASE_URI,
    pool_pre_ping=True,  # detect stale connections
    pool_size=2,
    max_overflow=1,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
