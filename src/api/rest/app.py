import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from src.api.rest.routes.assignment_routes import router as assignment_router
from src.api.rest.routes.client_routes import router as client_router
from src.api.rest.routes.client_rules_routes import router as client_rule_router
from src.api.rest.routes.content_extract_rotues import router as content_extract_router
from src.api.rest.routes.department_routes import router as department_router
from src.api.rest.routes.email_routes import router as email_router
from src.api.rest.routes.employee_rotues import router as employee_router
from src.api.rest.routes.timecard_routes import router as timecard_router
from src.api.rest.routes.timesheet_routes import router as timesheet_router
from src.core.exceptions import handlers as exception_handlers
from src.core.services.gmail_poller import GmailPoller
from src.data.clients import postgress_client
from src.data.clients.postgress_client import dispose_async_engine, init_async_engine

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_async_engine()
    if postgress_client.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized")

    gmail_poller = GmailPoller(session_factory=postgress_client.SessionLocal)
    gmail_poller_task = asyncio.create_task(gmail_poller.run())
    logger.info("Started Gmail poller background task")

    yield

    gmail_poller.stop()
    gmail_poller_task.cancel()
    with suppress(asyncio.CancelledError):
        await gmail_poller_task

    await dispose_async_engine()


def get_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    exception_handlers.register_exception_handlers(app)
    app.include_router(client_router)
    app.include_router(email_router)
    app.include_router(employee_router)
    app.include_router(timesheet_router)
    app.include_router(timecard_router)
    app.include_router(client_rule_router)
    app.include_router(department_router)
    app.include_router(assignment_router)
    app.include_router(content_extract_router)
    return app
