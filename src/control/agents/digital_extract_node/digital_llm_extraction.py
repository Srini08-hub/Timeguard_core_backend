import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq

from src.config.settings import settings
from src.control.agents.digital_extract_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.control.agents.timesheet_schema import MergeResponse
from src.core.exceptions.llm_exception import ExtractionError
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
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
        api_key=settings.GROQ_API_KEY_1,
        temperature=0,
    )
    structured_llm = llm.with_structured_output(MergeResponse)

    thread = list(messages)
    last_error = ""
    for attempt in range(1, max_retries + 2):
        try:
            response = structured_llm.invoke(_to_langchain_messages(thread, system_prompt))
            if not isinstance(response, MergeResponse):
                raise TypeError(
                    f"Invalid digital extraction response type: {type(response)!r}"
                )
            if attempt > 1:
                logger.info(
                    "Structured digital extraction succeeded on attempt %d/%d after retry",
                    attempt,
                    max_retries + 1,
                )
            return response
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Structured digital extraction attempt %d/%d failed: %s",
                attempt,
                max_retries + 1,
                exc,
            )
            if attempt <= max_retries:
                # thread = thread + [
                #     {
                #         "role": "user",
                #         "content": (
                #             "The previous structured extraction failed with this error:\n\n"
                #             f"{last_error}\n\n"
                #             "Fix only that issue and return data matching the "
                #             "structured schema."
                #         ),
                #     }
                # ]
                continue

    raise ExtractionError(
        message=(
            f"Structured digital extraction failed after {max_retries + 1} attempts."
            f" Last error: {last_error}"
        ),
        raw_response="",
        attempts=max_retries + 1,
    )


def _current_source(state: TimeguardState) -> tuple[str, str]:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index < len(attachments):
        file_name = attachments[index].get("file_name") or "unknown"
    else:
        file_name = "unknown"
    return file_name, "pdf"


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


async def _store_content_extract_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: dict[str, Any] | list[dict[str, Any]] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping content extract payload save because attachment index is out of range"
        )
        return

    attachment = attachments[index]
    content_extract_id = attachment.get("content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping content extract payload save because content_extract_id "
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
    logger.info("Stored digital extraction payload for content_extract %s", content_extract_id)


async def node_extract_block_with_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    blocks = state.get("d_blocks", [])
    if not isinstance(blocks, list):
        blocks = [blocks]

    system_prompt = build_system_prompt()
    file_name, content_type = _current_source(state)
    results: list[dict[str, Any]] = []
    extraction_failed = False
    failure_reason = None

    logger.info("Starting digital LLM extraction for %d block(s)", len(blocks))

    try:
        for block in blocks:
            messages = build_extraction_messages(
                block.text_payload,
                file_name=file_name,
                content_type=content_type,
            )

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
                logger.info("Digital block %d extracted successfully", block.block_index)
                results.append(
                    {
                        "block_index": block.block_index,
                        "success": True,
                        "extraction": parsed,
                        "error": None,
                        "raw_response_on_failure": None,
                    }
                )
                await _store_content_extract_payload(state, config, results[-1]["extraction"])
            except ExtractionError as e:
                logger.error(
                    "Digital block %d failed extraction permanently: %s",
                    block.block_index,
                    e,
                )
                extraction_failed = True
                failure_reason = str(e)
                results.append(
                    {
                        "block_index": block.block_index,
                        "success": False,
                        "extraction": None,
                        "error": str(e),
                        "raw_response_on_failure": e.raw_response,
                    }
                )
    except Exception as e:
        logger.exception("Unexpected error during digital LLM extraction: %s", e)
        extraction_failed = True
        failure_reason = str(e)
        results.append(
            {
                "block_index": 0 if blocks else 0,
                "success": False,
                "extraction": None,
                "error": str(e),
                "raw_response_on_failure": None,
            }
        )

    # Update email and attachment status if extraction failed
    if extraction_failed and failure_reason:
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        attachment_repository = AttachmentRepository(db_session)

        # Update email status
        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="digital_pdf_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set email %s status to FAILED due to digital extraction error", email_id
                )

        # Update attachment status
        attachments = state.get("attachments", [])
        index = state.get("current_attachment_index", 0)
        if index < len(attachments):
            attachment = attachments[index]
            attachment_db_id = attachment.get("attachment_db_id")
            if attachment_db_id:
                attachment_obj = await attachment_repository.get_by_id(attachment_db_id)
                if attachment_obj:
                    await attachment_repository.set_failed(
                        attachment_obj,
                        failure_stage="digital_pdf_extraction",
                        failure_reason=failure_reason,
                    )
                    logger.info(
                        "Set attachment %s status to FAILED due to digital extraction error",
                        attachment_db_id,
                    )

        await db_session.commit()

    trace_path = store_llm_result_for_testing(
        source="digital",
        payload=results,
        extra={"block_count": len(blocks)},
    )
    logger.info("Stored digital extraction result for testing at %s", trace_path)

    return state
