from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config.settings import settings
from src.core.services.excel_extraction_strategy_service import (
    excel_extraction_strategy_service,
)
from src.core.services.gmail_service import GmailService
from src.data.repositories.email_pool_repository import EmailPoolStateRepository
from src.workers.tasks.email_tasks import classify_email

logger = logging.getLogger(__name__)


class GmailPoller:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        poll_interval_seconds: int,
        gmail_service: GmailService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._gmail_service = gmail_service or GmailService()
        self._mailbox_address = settings.GMAIL_POLL_MAILBOX_ADDRESS
        self._poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run(self) -> None:
        logger.info(
            "Starting Gmail poller with interval=%s seconds",
            self._poll_interval_seconds,
        )
        while not self._stop_event.is_set():
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Gmail poller iteration failed")

            if self._stop_event.is_set():
                break

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except TimeoutError:
                continue

        logger.info("Gmail poller stopped")

    async def poll_once(self) -> None:
        async with self._session_factory() as session:
            repository = EmailPoolStateRepository(session)
            # mailbox_address = await self._resolve_mailbox_address(repository)
            mailbox_address = self._mailbox_address
            poll_state = await repository.get_by_mailbox(mailbox_address)

            # if poll_state is None or poll_state.last_history_id is None:
            #     profile = await asyncio.to_thread(self._gmail_service.get_profile)
            #     profile_history_id = profile.get("historyId")
            #     if profile_history_id is None:
            #         raise RuntimeError("Gmail profile did not include a historyId")

            #     await repository.update_history_id(mailbox_address,
            #    str(profile_history_id))
            #     await session.commit()
            #     logger.info(
            #         "Initialized Gmail poll state for mailbox=%s history_id=%s",
            #         mailbox_address,
            #         profile_history_id,
            #     )
            #     return

            try:
                if poll_state is None:
                    raise ValueError("Poll state not found")

                if poll_state.last_history_id is None:
                    raise ValueError("last_history_id is not set")
                history_payload = await asyncio.to_thread(
                    self._gmail_service.get_history,
                    poll_state.last_history_id,
                )
            except HttpError as exc:
                if getattr(exc.resp, "status", None) == 404:
                    profile = await asyncio.to_thread(self._gmail_service.get_profile)
                    profile_history_id = profile.get("historyId")
                    if profile_history_id is None:
                        raise RuntimeError(
                            "Gmail profile did not include a historyId"
                        ) from exc

                    await repository.update_history_id(
                        mailbox_address,
                        str(profile_history_id),
                    )
                    await session.commit()
                    logger.warning(
                        "Reset Gmail poll state for mailbox=%s because history_id expired",
                        mailbox_address,
                    )
                    return

                raise
            logger.info("Fetched Gmail history: %s", history_payload)
            newest_history_id = history_payload.get("historyId")
            if newest_history_id is None:
                raise RuntimeError("Gmail history response did not include historyId")

            message_ids = self._extract_message_ids(history_payload.get("history", []))
            logger.info(
                "Fetched Gmail history for mailbox=%s messages=%s newest_history_id=%s",
                mailbox_address,
                len(message_ids),
                newest_history_id,
            )

            for message_id in message_ids:
                # classify_email.apply_async(
                #     args=[message_id],
                #     queue=settings.CELERY_TASK_QUEUE_NAME,
                # )
                classify_email.delay(
                    message_id,
                    excel_extraction_strategy_service.get_strategy(),
                )
                logger.info(
                    "Queued email %s with Excel strategy %s",
                    message_id,
                    excel_extraction_strategy_service.get_strategy(),
                )

            if mailbox_address is not None and newest_history_id is not None:
                await repository.update_history_id(mailbox_address, str(newest_history_id))
                await session.commit()
            logger.info(
                "Updated Gmail poll state for mailbox=%s history_id=%s",
                mailbox_address,
                newest_history_id,
            )

    @staticmethod
    def _extract_message_ids(history_entries: Sequence[dict[str, object]]) -> list[str]:
        message_ids: list[str] = []
        seen_message_ids: set[str] = set()

        for entry in history_entries:
            messages_added = entry.get("messagesAdded", [])
            if not isinstance(messages_added, list):
                continue

            for message_added in messages_added:
                if not isinstance(message_added, dict):
                    continue

                message = message_added.get("message")
                if not isinstance(message, dict):
                    continue

                message_id = message.get("id")
                if not isinstance(message_id, str) or message_id in seen_message_ids:
                    continue

                seen_message_ids.add(message_id)
                message_ids.append(message_id)

        return message_ids
