"""Vision-based structured timesheet extraction from image attachments."""

from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.image_extract_node.prompts import (
    build_extraction_messages,
    build_system_prompt,
)
from src.control.agents.state import AttachmentState, TimeguardState
from src.control.agents.timesheet_schema import MergeResponse
from src.core.exceptions.llm_exception import ExtractionError
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository
from src.utils.storage import resolve_attachment_to_local_path

# from src.llm_trace_debug import store_llm_result_for_testing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 2
MODEL_NAME = "gemini-3.5-flash"


def _to_langchain_messages(messages: list[dict], system: str) -> list:
    lc_messages: list = [SystemMessage(content=system)]
    for message in messages:
        role = message["role"]
        content = message["content"]
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            if not isinstance(content, str):
                raise ValueError("Assistant message content must be a string")
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
    llm = ChatGoogleGenerativeAI(
        model=MODEL_NAME,
        temperature=0,
        api_key=settings.GOOGLE_API_KEY,
    )
    structured_llm = llm.with_structured_output(MergeResponse)

    thread = list(messages)
    last_error = ""
    for attempt in range(1, max_retries + 2):
        try:
            response = structured_llm.invoke(_to_langchain_messages(thread, system_prompt))
            if not isinstance(response, MergeResponse):
                raise TypeError(f"Invalid image extraction response type: {type(response)!r}")
            if attempt > 1:
                logger.info(
                    "Structured image extraction succeeded on attempt %d/%d",
                    attempt,
                    max_retries + 1,
                )
            return response
        except Exception as exc:
            last_error = str(exc)
            logger.warning(
                "Structured image extraction attempt %d/%d failed: %s",
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
            f"Structured image extraction failed after {max_retries + 1} attempts."
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


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        raise ValueError("No attachment available for image extraction")
    return attachments[index]


# def _resolve_attachment_path(attachment: AttachmentState) -> Path:
#     attachment_url = attachment.get("attachment_url")
#     if attachment_url:
#         parsed_url = urlparse(attachment_url)
#         candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
#         if candidate.exists():
#             return candidate

#     file_name = attachment.get("file_name")
#     if file_name:
#         matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
#         if matches:
#             return matches[0]

#     raise FileNotFoundError(
#         f"Unable to resolve a stored "
#         f"file for attachment {attachment.get('file_name', '<unknown>')}"
#     )


def _load_image_for_llm(image_path: Path) -> tuple[str, bytes]:
    if not image_path.is_file():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    media_type, _ = mimetypes.guess_type(image_path.name)
    return (media_type or "application/octet-stream", image_path.read_bytes())


async def _store_content_extract_payload(
    state: TimeguardState,
    config: RunnableConfig,
    payload: list[Any] | dict[str, Any] | None,
) -> None:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        logger.warning(
            "Skipping image content extract payload save "
            "because attachment index is out of range"
        )
        return

    attachment = attachments[index]
    content_extract_id = attachment.get("content_extract_id")
    if content_extract_id is None:
        logger.warning(
            "Skipping image content extract payload save because "
            "content_extract_id is missing for attachment %s",
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
    logger.info("Stored image extraction payload for content_extract %s", content_extract_id)


async def _mark_image_extraction_failed(
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
                failure_stage="image_extraction",
                failure_reason=failure_reason,
            )
            logger.info(
                "Set email %s status to FAILED due to image extraction error",
                email_id,
            )
        else:
            logger.warning("Email %s not found for image failure update", email_id)

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
                    failure_stage="image_extraction",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to image extraction error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for image failure update",
                    attachment_db_id,
                )

    await db_session.commit()


async def image_extraction_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    attachment: AttachmentState | None = None

    try:
        attachment = _current_attachment(state)
        # image_path = _resolve_attachment_path(attachment)
        image_path = resolve_attachment_to_local_path(attachment)
        media_type, image_bytes = _load_image_for_llm(image_path)
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        file_name = attachment.get("file_name") or "unknown"
        content_type = "image"

        logger.info(
            "Starting image LLM extraction for attachment %s from %s",
            file_name,
            image_path,
        )

        system_prompt = build_system_prompt()
        messages = build_extraction_messages(
            media_type,
            image_base64,
            file_name=file_name,
            content_type=content_type,
        )

        response = _extract_structured(
            system_prompt=system_prompt,
            messages=messages,
        )
        parsed = response.model_dump()
        # parsed = _apply_source_metadata(
        #     response.model_dump(),
        #     file_name=file_name,
        #     content_type=content_type,
        # )
        await _store_content_extract_payload(state, config, parsed)

        # trace_path = store_llm_result_for_testing(
        #     source="image",
        #     payload=parsed,
        #     extra={"file_name": file_name},
        # )
        # logger.info("Stored image extraction result for testing at %s", trace_path)
    except ExtractionError as exc:
        logger.error(
            "Image extraction failed permanently for attachment %s: %s",
            attachment.get("file_name", "<unknown>") if attachment else "<unknown>",
            exc,
        )
        # store_llm_result_for_testing(
        #     source="image",
        #     payload={
        #         "success": False,
        #         "error": str(exc),
        #         "raw_response_on_failure": exc.raw_response,
        #     },
        #     extra={"file_name": attachment.get("file_name", "") if attachment else ""},
        # )
        await _mark_image_extraction_failed(state, config, str(exc))
        raise exc
    except Exception as exc:
        logger.exception(
            "Image extraction failed for attachment %s: %s",
            attachment.get("file_name", "<unknown>") if attachment else "<unknown>",
            exc,
        )
        # store_llm_result_for_testing(
        #     source="image",
        #     payload={
        #         "success": False,
        #         "error": str(exc),
        #         "raw_response_on_failure": None,
        #     },
        #     extra={"file_name": attachment.get("file_name", "") if attachment else ""},
        # )
        await _mark_image_extraction_failed(state, config, str(exc))
        raise exc

    return state
