from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.exceptions import handlers as exception_handlers
from src.data.clients.postgress_client import dispose_async_engine, init_async_engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_async_engine()
    yield
    await dispose_async_engine()


def get_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    # register all app-specific exception handlers centrally
    # setup_cors(app)
    exception_handlers.register_exception_handlers(app)
    return app
