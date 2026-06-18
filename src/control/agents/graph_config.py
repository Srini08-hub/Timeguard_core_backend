from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.services.gmail_service import GmailService

DB_SESSION_CONFIG_KEY = "db_session"
GMAIL_SERVICE_CONFIG_KEY = "gmail_service"


def get_db_session(config: RunnableConfig) -> AsyncSession:
    configurable = config.get("configurable") or {}
    session = configurable.get(DB_SESSION_CONFIG_KEY)
    if session is None:
        raise RuntimeError(
            f"Missing '{DB_SESSION_CONFIG_KEY}' in LangGraph config.configurable"
        )
    if not isinstance(session, AsyncSession):
        raise TypeError(
            f"Expected AsyncSession for '{DB_SESSION_CONFIG_KEY}', "
            f"got {type(session).__name__}"
        )
    return session


def get_gmail_service(config: RunnableConfig) -> GmailService:
    configurable = config.get("configurable") or {}
    service = configurable.get(GMAIL_SERVICE_CONFIG_KEY)
    if service is None:
        raise RuntimeError(
            f"Missing '{GMAIL_SERVICE_CONFIG_KEY}' in LangGraph config.configurable"
        )
    if not isinstance(service, GmailService):
        raise TypeError(
            f"Expected GmailService for '{GMAIL_SERVICE_CONFIG_KEY}', "
            f"got {type(service).__name__}"
        )
    return service
