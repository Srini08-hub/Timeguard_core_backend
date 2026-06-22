"""Vision-based timesheet extraction from image attachments."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain_core.runnables import RunnableConfig

from src.config.settings import settings
from src.control.agents.digital_extract_node.llm_client import (
    ExtractionError,
    extract_with_retries,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.image_extract_node.gemini_caller import call_gemini_vision
from src.control.agents.image_extract_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        raise ValueError("No attachment available for image extraction")
    return attachments[index]


def _resolve_attachment_path(attachment: AttachmentState) -> Path:
    attachment_url = attachment.get("attachment_url")
    if attachment_url:
        parsed_url = urlparse(attachment_url)
        candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
        if candidate.exists():
            return candidate

    file_name = attachment.get("file_name")
    if file_name:
        matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
        if matches:
            return matches[0]

    raise FileNotFoundError(
        f"Unable to resolve a stored "
        f"file for attachment {attachment.get('file_name', '<unknown>')}"
    )


def _load_image_for_llm(image_path: Path) -> tuple[str, bytes]:
    if not image_path.is_file():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    media_type, _ = mimetypes.guess_type(image_path.name)
    return (media_type or "application/octet-stream", image_path.read_bytes())


async def _store_timesheet_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: list[Any] | dict[str, Any] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping image timesheet payload save "
            "because attachment index is out of range"
        )
        return

    attachment = attachments[index]
    timesheet_id = attachment.get("timesheet_id")
    if timesheet_id is None:
        logger.warning(
            "Skipping image timesheet payload save because "
            "timesheet_id is missing for attachment %s",
            attachment.get("file_name", "<unknown>"),
        )
        return

    db_session = get_db_session(config)
    timesheet_repository = TimesheetRepository(db_session)
    timesheet = await timesheet_repository.set_extracted_payload(
        timesheet_id=timesheet_id,
        extracted_payload={"extraction": payload},
    )
    if timesheet is None:
        return

    await db_session.commit()
    logger.info("Stored image extraction payload for timesheet %s", timesheet_id)


async def image_extraction_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    attachment = _current_attachment(state)
    image_path = _resolve_attachment_path(attachment)
    media_type, image_bytes = _load_image_for_llm(image_path)
    image_base64 = base64.b64encode(image_bytes).decode("ascii")

    logger.info(
        "Starting image LLM extraction for attachment %s from %s",
        attachment.get("file_name", ""),
        image_path,
    )

    system_prompt = build_system_prompt()
    messages = build_extraction_messages(media_type, image_base64)

    try:
        parsed = extract_with_retries(
            call_llm=call_gemini_vision,
            system_prompt=system_prompt,
            messages=messages,
        )
        await _store_timesheet_payload(state, config, parsed)

        trace_path = store_llm_result_for_testing(
            source="image",
            payload=parsed,
            extra={"file_name": attachment.get("file_name", "")},
        )
        logger.info("Stored image extraction result for testing at %s", trace_path)
    except ExtractionError as exc:
        logger.error(
            "Image extraction failed permanently for attachment %s: %s",
            attachment.get("file_name", "<unknown>"),
            exc,
        )
        store_llm_result_for_testing(
            source="image",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": exc.raw_response,
            },
            extra={"file_name": attachment.get("file_name", "")},
        )

    return state
