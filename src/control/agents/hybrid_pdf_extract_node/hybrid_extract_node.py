from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langchain_core.runnables import RunnableConfig
from llama_parse import LlamaParse

from src.config.settings import settings
from src.control.agents.excel_extract_node.groq_caller import call_groq
from src.control.agents.excel_extract_node.llm_client import (
    ExtractionError,
    extract_with_retries,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.hybrid_pdf_extract_node.prompts import (
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
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


def _resolve_attachment_path(attachment: AttachmentState) -> Path | None:
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
    return None


def _parse_pdf_to_markdown(pdf_path: Path) -> tuple[str, int]:
    parser = LlamaParse(
        api_key=settings.LLAMA_CLOUD_API_KEY,
        result_type="markdown",
    )
    documents = parser.load_data(str(pdf_path))
    if not documents:
        raise ValueError(f"LlamaParse returned no pages for file: {pdf_path}")

    page_sections: list[str] = []
    for page_index, document in enumerate(documents, start=1):
        page_text = str(getattr(document, "text", "")).strip()
        page_sections.append(f"## Page {page_index}\n{page_text}")

    markdown_payload = "\n\n".join(page_sections).strip()
    return markdown_payload, len(documents)


def _write_markdown_payload(markdown_payload: str, pdf_path: Path) -> Path:
    markdown_path = pdf_path.with_suffix(".md")
    markdown_path.write_text(markdown_payload, encoding="utf-8")
    return markdown_path


async def _store_content_extract_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: dict[str, Any] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping hybrid PDF payload save because attachment index is out of range"
        )
        return

    attachment = attachments[index]
    content_extract_id = attachment.get("content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping hybrid PDF payload save because content_extract_id "
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
        "Stored hybrid PDF extraction payload for content_extract %s",
        content_extract_id,
    )


async def _mark_llm_extraction_failed(
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
                failure_stage="hybrid_pdf_extraction",
                failure_reason=failure_reason,
            )
            logger.info(
                "Set email %s status to FAILED due to hybrid PDF extraction error",
                email_id,
            )
        else:
            logger.warning("Email %s not found for hybrid PDF failure update", email_id)

    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index < len(attachments):
        attachment = attachments[index]
        attachment_db_id = attachment.get("attachment_db_id")
        if attachment_db_id:
            attachment_obj = await attachment_repository.get_by_id(attachment_db_id)
            if attachment_obj is not None:
                await attachment_repository.set_failed(
                    attachment_obj,
                    failure_stage="hybrid_pdf_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to hybrid PDF extraction error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for hybrid PDF failure update",
                    attachment_db_id,
                )

    await db_session.commit()


async def hybrid_pdf_extraction_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    """Parse hybrid PDF to markdown with LlamaParse, then extract JSON with Groq."""
    attachment = _current_attachment(state)
    file_path = _resolve_attachment_path(attachment)
    if file_path is None:
        raise ValueError("Could not resolve attachment path for hybrid PDF extraction")

    logger.info(
        "Starting hybrid PDF extraction for attachment %s from %s",
        attachment.get("file_name", ""),
        file_path,
    )

    markdown_payload, page_count = _parse_pdf_to_markdown(file_path)
    markdown_path = _write_markdown_payload(markdown_payload, file_path)

    system_prompt = build_system_prompt()
    messages = build_extraction_messages(markdown_payload)

    try:
        parsed = extract_with_retries(
            call_llm=call_groq,
            system_prompt=system_prompt,
            messages=messages,
        )
    except ExtractionError as exc:
        logger.error(
            "Hybrid PDF extraction failed permanently for attachment %s: %s",
            attachment.get("file_name", "<unknown>"),
            exc,
        )
        store_llm_result_for_testing(
            source="hybrid_pdf",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": exc.raw_response,
            },
            extra={
                "file_name": attachment.get("file_name", ""),
                "page_count": page_count,
                "markdown_path": str(markdown_path),
            },
        )
        await _mark_llm_extraction_failed(state, config, str(exc))
        return state
    except Exception as exc:
        logger.exception(
            "Unexpected hybrid PDF LLM extraction error for attachment %s: %s",
            attachment.get("file_name", "<unknown>"),
            exc,
        )
        store_llm_result_for_testing(
            source="hybrid_pdf",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": None,
            },
            extra={
                "file_name": attachment.get("file_name", ""),
                "page_count": page_count,
                "markdown_path": str(markdown_path),
            },
        )
        await _mark_llm_extraction_failed(state, config, str(exc))
        raise exc

    await _store_content_extract_payload(state, config, parsed)

    trace_path = store_llm_result_for_testing(
        source="hybrid_pdf",
        payload=parsed,
        extra={
            "file_name": attachment.get("file_name", ""),
            "page_count": page_count,
            "markdown_path": str(markdown_path),
        },
    )
    logger.info("Stored hybrid PDF extraction result for testing at %s", trace_path)

    return state
