import asyncio
import logging
from collections.abc import Coroutine

# from collections.abc import Coroutine
from typing import Any, TypeVar

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown

from src.config.settings import settings
from src.data.clients.postgress_client import dispose_async_engine, init_async_engine

celery_app = Celery(
    "core_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_serializer="json",
    timezone="UTC",
)

celery_app.autodiscover_tasks(["src.workers"])

logger = logging.getLogger(__name__)

T = TypeVar("T")
_worker_loop: asyncio.AbstractEventLoop | None = None


def run_async[T](coro: Coroutine[Any, Any, T]) -> T:
    if _worker_loop is None:
        raise RuntimeError("Celery worker event loop is not initialized")
    return _worker_loop.run_until_complete(coro)


@worker_process_init.connect
def init_worker_db(**kwargs: object) -> None:
    global _worker_loop
    _worker_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_worker_loop)
    init_async_engine()
    logger.info("Initialized async database engine for Celery worker")


@worker_process_shutdown.connect
def shutdown_worker_db(**kwargs: object) -> None:
    global _worker_loop
    if _worker_loop is not None:
        _worker_loop.run_until_complete(dispose_async_engine())
        _worker_loop.close()
        _worker_loop = None
        asyncio.set_event_loop(None)
    logger.info("Disposed async database engine for Celery worker")
