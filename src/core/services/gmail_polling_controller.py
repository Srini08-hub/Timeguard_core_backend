from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.core.services.gmail_poller import GmailPoller

logger = logging.getLogger(__name__)


class GmailPollingController:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._poller: GmailPoller | None = None
        self._task: asyncio.Task[None] | None = None
        self._interval_seconds: int | None = None

    def status(self) -> dict[str, bool | int | None]:
        return {
            "running": self._task is not None and not self._task.done(),
            "interval_seconds": self._interval_seconds,
        }

    async def start(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        interval_seconds: int,
    ) -> None:
        async with self._lock:
            await self._stop_locked()

            self._poller = GmailPoller(
                session_factory=session_factory,
                poll_interval_seconds=interval_seconds,
            )
            self._interval_seconds = interval_seconds
            self._task = asyncio.create_task(self._poller.run())
            logger.info("Started Gmail poller with interval=%s seconds", interval_seconds)

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        poller = self._poller
        task = self._task

        self._poller = None
        self._task = None
        self._interval_seconds = None

        if poller is not None:
            poller.stop()

        if task is None:
            return

        if not task.done():
            task.cancel()

        with suppress(asyncio.CancelledError):
            try:
                await task
            except Exception:
                logger.exception("Gmail poller task ended with an error")


gmail_polling_controller = GmailPollingController()
