"""Groq-based timesheet JSON extraction from email subject and body."""

from __future__ import annotations

import logging
from typing import Any

from core_backend.src.control.agents.extract_email_body_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from langchain_core.runnables import RunnableConfig

from src.control.agents.digital_extract_node.llm_client import (
    ExtractionError,
    extract_with_retries,
)
from src.control.agents.excel_extract_node.groq_caller import call_groq
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.repositories.timesheet_repository import TimesheetRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _store_body_timesheet_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: dict[str, Any] | list[Any] | None,
) -> None:
    timesheet_id = state.get("email_body_timesheet_id")
    if timesheet_id is None:
        logger.warning(
            "Skipping email body timesheet payload save because"
            " email_body_timesheet_id is missing"
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
    logger.info("Stored email body extraction payload for timesheet %s", timesheet_id)


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

    try:
        parsed = extract_with_retries(
            call_llm=call_groq,
            system_prompt=system_prompt,
            messages=messages,
        )
        await _store_body_timesheet_payload(state, config, parsed)

        trace_path = store_llm_result_for_testing(
            source="email_body",
            payload=parsed,
            extra={"gmail_message_id": state.get("gmail_message_id", "")},
        )
        logger.info("Stored email body extraction result for testing at %s", trace_path)
    except ExtractionError as exc:
        logger.error("Email body extraction failed permanently: %s", exc)
        store_llm_result_for_testing(
            source="email_body",
            payload={
                "success": False,
                "error": str(exc),
                "raw_response_on_failure": exc.raw_response,
            },
            extra={"gmail_message_id": state.get("gmail_message_id", "")},
        )

    return state
