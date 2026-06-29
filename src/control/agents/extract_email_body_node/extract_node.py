"""Groq-based timesheet JSON extraction from email subject and body."""

from __future__ import annotations

import logging
from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from src.control.agents.digital_extract_node.llm_client import (
    ExtractionError,
    extract_with_retries,
)
from src.control.agents.excel_extract_node.groq_caller import call_groq
from src.control.agents.extract_email_body_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _store_body_content_extract_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: dict[str, Any] | list[Any] | None,
) -> None:
    content_extract_id = state.get("email_body_content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping email body content extract payload save because"
            " email_body_content_extract_id is missing"
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
        "Stored email body extraction payload for content_extract %s", content_extract_id
    )


async def email_body_extraction_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    subject = state.get("subject", "")
    body = state.get("body", "")

    logger.info(
        "Starting email body LLM extraction (subject=%d chars, body=%d chars)",
        len(subject),
        len(body),
    )

    system_prompt = build_system_prompt()
    messages = build_extraction_messages(subject, body)

    extraction_failed = False
    failure_reason = None

    try:
        parsed = extract_with_retries(
            call_llm=call_groq,
            system_prompt=system_prompt,
            messages=messages,
        )
        await _store_body_content_extract_payload(state, config, parsed)

        trace_path = store_llm_result_for_testing(
            source="email_body",
            payload=parsed,
            extra={"gmail_message_id": state.get("gmail_message_id", "")},
        )
        logger.info("Stored email body extraction result for testing at %s", trace_path)

        # Update email status to EXTRACTED
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(email, EmailStatus.EXTRACTED)
                logger.info("Set email %s status to EXTRACTED", email_id)
        await db_session.commit()

        # Mark email body extraction as complete
        result = cast(TimeguardState, {**state, "email_body_extracted": True})
        return result
    except ExtractionError as exc:
        logger.error("Email body extraction failed permanently: %s", exc)
        extraction_failed = True
        failure_reason = str(exc)
        store_llm_result_for_testing(
            source="email_body",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": exc.raw_response,
            },
            extra={"gmail_message_id": state.get("gmail_message_id", "")},
        )
    except Exception as e:
        logger.exception("Unexpected error during email body extraction: %s", e)
        extraction_failed = True
        failure_reason = str(e)
        store_llm_result_for_testing(
            source="email_body",
            payload={
                "success": False,
                "error": str(e),
                "raw_response_on_failure": None,
            },
            extra={"gmail_message_id": state.get("gmail_message_id", "")},
        )

    # Update email and attachment status if extraction failed
    if extraction_failed and failure_reason:
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        # attachment_repository = AttachmentRepository(db_session)

        # Update email status
        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="email_body_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set email %s status to FAILED due to email body extraction error",
                    email_id,
                )

        # # Update attachment status for email body (if applicable)
        # attachments = state.get("attachments", [])
        # for attachment in attachments:
        #     attachment_db_id = attachment.get("attachment_db_id")
        #     if attachment_db_id:
        #         attachment_obj = await attachment_repository.get_by_id(attachment_db_id)
        #         if attachment_obj:
        #             await attachment_repository.set_status(
        #                 attachment_obj,
        #                 AttachmentStatus.FAILED,
        #                 failure_stage="email_body_extraction",
        #                 failure_reason=failure_reason,
        #             )
        #             logger.info(
        #                 "Set attachment %s status to FAILED due to email body extraction
        #  error",
        #                 attachment_db_id
        #             )

        await db_session.commit()
        raise Exception(f"Email body extraction failed: {failure_reason}")

    # Still mark as extracted even if it failed, so we can proceed to merge
    result = cast(TimeguardState, {**state, "email_body_extracted": True})
    return result
