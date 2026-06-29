"""Vision-based timesheet extraction from scanned PDF attachments."""

from __future__ import annotations

import logging
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
from src.control.agents.scanned_pdf_extraction_node.pdf_to_images import (
    render_pdf_pages,
)
from src.control.agents.scanned_pdf_extraction_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        raise ValueError("No attachment available for scanned PDF extraction")
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
        f"Unable to resolve a stored file for attachment "
        f"{attachment.get('file_name', '<unknown>')}"
    )


async def _store_content_extract_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: dict[str, Any] | list[Any] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping scanned PDF content extract payload save because attachment "
            "index is out of range"
        )
        return

    attachment = attachments[index]
    content_extract_id = attachment.get("content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping scanned PDF content extract payload save"
            "because content_extract_id "
            "is missing for attachment %s",
            attachment.get("file_name", "<unknown>"),
        )
        return

    db_session = get_db_session(config)
    content_extract_repository = ContentExtractRepository(db_session)
    content_extract = await content_extract_repository.set_extracted_payload(
        content_extract_id=content_extract_id,
        extracted_payload={"extraction": payload},
    )
    if content_extract is None:
        return

    await db_session.commit()
    logger.info(
        "Stored scanned PDF extraction payload for content_extract %s", content_extract_id
    )


async def _mark_scanned_pdf_extraction_failed(
    state: TimeguardState,
    config: RunnableConfig,
    failure_reason: str,
) -> None:
    db_session = get_db_session(config)
    email_repository = EmailRepository(db_session)
    attachment_repository = AttachmentRepository(db_session)

    email_id = state.get("email_id")
    if email_id:
        email = await email_repository.get_by_id(email_id)
        if email is not None:
            await email_repository.set_status(
                email,
                EmailStatus.FAILED,
                failure_stage="scanned_pdf_extraction",
                failure_reason=failure_reason,
            )
            logger.info(
                "Set email %s status to FAILED due to scanned PDF extraction error",
                email_id,
            )
        else:
            logger.warning(
                "Email %s not found for scanned PDF extraction failure update", email_id
            )

    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index < len(attachments):
        attachment_state = attachments[index]
        attachment_db_id = attachment_state.get("attachment_db_id")
        if attachment_db_id:
            attachment = await attachment_repository.get_by_id(attachment_db_id)
            if attachment is not None:
                await attachment_repository.set_failed(
                    attachment,
                    failure_stage="scanned_pdf_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to scanned PDF extraction error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for scanned PDF extraction failure update",
                    attachment_db_id,
                )

    await db_session.commit()


async def scanned_pdf_extraction_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    attachment = _current_attachment(state)
    pdf_path = _resolve_attachment_path(attachment)
    rendered_pages = render_pdf_pages(pdf_path)

    if not rendered_pages:
        logger.warning(
            "Scanned PDF %s has no pages; skipping extraction",
            attachment.get("file_name", ""),
        )
        return state

    logger.info(
        "Starting scanned PDF LLM extraction for attachment %s from %s (%d page(s))",
        attachment.get("file_name", ""),
        pdf_path,
        len(rendered_pages),
    )

    system_prompt = build_system_prompt()
    page_tuples = [
        (page.page_number, page.media_type, page.image_base64) for page in rendered_pages
    ]
    messages = build_extraction_messages(page_tuples)

    try:
        parsed = extract_with_retries(
            call_llm=call_gemini_vision,
            system_prompt=system_prompt,
            messages=messages,
        )
    except ExtractionError as exc:
        logger.error(
            "Scanned PDF extraction failed permanently for attachment %s: %s",
            attachment.get("file_name", "<unknown>"),
            exc,
        )
        store_llm_result_for_testing(
            source="scanned_pdf",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": exc.raw_response,
            },
            extra={
                "file_name": attachment.get("file_name", ""),
                "page_count": len(rendered_pages),
            },
        )
        await _mark_scanned_pdf_extraction_failed(state, config, str(exc))
        return state
    except Exception as exc:
        logger.exception(
            "Unexpected scanned PDF LLM extraction error for attachment %s: %s",
            attachment.get("file_name", "<unknown>"),
            exc,
        )
        store_llm_result_for_testing(
            source="scanned_pdf",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": None,
            },
            extra={
                "file_name": attachment.get("file_name", ""),
                "page_count": len(rendered_pages),
            },
        )
        await _mark_scanned_pdf_extraction_failed(state, config, str(exc))
        return state

    await _store_content_extract_payload(state, config, parsed)

    trace_path = store_llm_result_for_testing(
        source="scanned_pdf",
        payload=parsed,
        extra={
            "file_name": attachment.get("file_name", ""),
            "page_count": len(rendered_pages),
        },
    )
    logger.info("Stored scanned PDF extraction result for testing at %s", trace_path)

    return state
