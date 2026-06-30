"""Groq-based structured timesheet extraction from email subject and body."""

from __future__ import annotations

import logging
from typing import Any, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

from src.config.settings import settings
from src.control.agents.extract_email_body_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.control.agents.timesheet_schema import MergeResponse
from src.core.exceptions.llm_exception import ExtractionError
from src.data.models.email import EmailStatus
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MODEL_NAME = "llama-3.3-70b-versatile"


def _to_langchain_messages(messages: list[dict], system: str) -> list:
    lc_messages: list = [SystemMessage(content=system)]
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            raise ValueError(f"Unexpected message role: {role!r}")
    return lc_messages


def _extract_structured(
    *,
    system_prompt: str,
    messages: list[dict],
    max_retries: int = MAX_RETRIES,
) -> MergeResponse:
    llm = ChatGroq(
        model_name=MODEL_NAME,
        api_key=settings.GROQ_API_KEY_2,
        temperature=0,
        max_tokens=4096,
    )
    structured_llm = llm.with_structured_output(MergeResponse)

    thread = list(messages)
    last_error = ""
    for attempt in range(1, max_retries + 2):
        try:
            response = structured_llm.invoke(_to_langchain_messages(thread, system_prompt))
            if not isinstance(response, MergeResponse):
                raise TypeError(
                    f"Invalid email body extraction response type: {type(response)!r}"
                )
            if attempt > 1:
                logger.info(
                    "Structured email body extraction succeeded on attempt %d/%d",
                    attempt,
                    max_retries + 1,
                )
            return response
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Structured email body extraction attempt %d/%d failed: %s",
                attempt,
                max_retries + 1,
                exc,
            )
            if attempt <= max_retries:
                thread = thread + [
                    {
                        "role": "user",
                        "content": (
                            "The previous structured extraction failed with this error:\n\n"
                            f"{last_error}\n\n"
                            "Fix only that issue and return data matching the "
                            "structured schema."
                        ),
                    }
                ]

    raise ExtractionError(
        message=(
            f"Structured email body extraction failed after {max_retries + 1} attempts."
            f" Last error: {last_error}"
        ),
        raw_response="",
        attempts=max_retries + 1,
    )


def _apply_source_metadata(
    payload: dict[str, Any],
    *,
    file_name: str,
    content_type: str,
) -> dict[str, Any]:
    source = {"file_name": file_name, "content_type": content_type}
    employee_records = payload.get("employee_records")
    if isinstance(employee_records, list):
        for employee_record in employee_records:
            if isinstance(employee_record, dict):
                employee_record["source"] = [source]
    return payload


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
    file_name = "email"
    content_type = "email"

    logger.info(
        "Starting email body LLM extraction (subject=%d chars, body=%d chars)",
        len(subject),
        len(body),
    )

    system_prompt = build_system_prompt()
    messages = build_extraction_messages(
        subject,
        body,
        file_name=file_name,
        content_type=content_type,
    )

    extraction_failed = False
    failure_reason = None

    try:
        response = _extract_structured(
            system_prompt=system_prompt,
            messages=messages,
        )
        parsed = _apply_source_metadata(
            response.model_dump(),
            file_name=file_name,
            content_type=content_type,
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

    # Update email status if extraction failed
    if extraction_failed and failure_reason:
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)

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

        await db_session.commit()
        raise Exception(f"Email body extraction failed: {failure_reason}")

    result = cast(TimeguardState, {**state, "email_body_extracted": True})
    return result
