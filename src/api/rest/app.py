import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

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
    # app.state.gmail_poller = gmail_poller
    # app.state.gmail_poller_task = gmail_poller_task
    logger.info("Started Gmail poller background task")

    yield

    gmail_poller.stop()
    gmail_poller_task.cancel()
    with suppress(asyncio.CancelledError):
        await gmail_poller_task

    await dispose_async_engine()


def get_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # register all app-specific exception handlers centrally
    # setup_cors(app)
    exception_handlers.register_exception_handlers(app)
    return app
