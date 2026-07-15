import logging
from enum import StrEnum
from typing import cast
from uuid import UUID

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus
from src.data.models.email import EmailClassificationStatus, EmailStatus
from src.data.repositories.content_extract_repository import ContentExtractRepository
from src.data.repositories.email_repository import EmailRepository

logger = logging.getLogger(__name__)

ANCHOR_KEYWORDS = [
    "timesheet",
    "time sheet",
    "hours worked",
    "total hours",
    "week ending",
    "overtime",
    "pay period",
    "time in",
    "time out",
    "billable hours",
    "clock in",
    "clock out",
    "attendance",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "employee",
    "project code",
    "approved",
    "supervisor",
]
FUZZY_THRESHOLD = 88
CONTEXT_CHARS = 100
SHORT_BODY_CHAR_THRESHOLD = 50


class EmailBodyClassification(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class EmailBodyClassificationResponse(BaseModel):
    classification: EmailBodyClassification = Field(
        description="Whether the email body indicates a timesheet."
    )


def _find_keyword_position(
    keyword: str,
    text: str,
    threshold: float,
) -> tuple[bool, float, int]:
    keyword_lower = keyword.lower()
    text_lower = text.lower()
    index = text_lower.find(keyword_lower)
    if index != -1:
        return True, 100.0, index

    window_size = len(keyword_lower) + 10
    best_score = 0.0
    best_position = -1
    for index in range(0, max(1, len(text_lower) - window_size + 1), 5):
        chunk = text_lower[index : index + window_size]
        score = float(fuzz.token_set_ratio(keyword_lower, chunk))
        if score > best_score:
            best_score = score
            best_position = index

    if best_score >= threshold:
        return True, best_score, best_position

    return False, 0.0, -1


def _fuzzy_match_anchors(body: str, subject: str = "") -> list[dict]:
    hits = []
    combined_text = f"{subject}\n{body}" if subject else body

    for keyword in ANCHOR_KEYWORDS:
        found, score, position = _find_keyword_position(
            keyword,
            combined_text,
            FUZZY_THRESHOLD,
        )
        if found:
            hits.append(
                {
                    "keyword": keyword,
                    "score": score,
                    "position": position,
                }
            )

    return sorted(
        hits,
        key=lambda hit: hit["score"] if isinstance(hit["score"], (int, float)) else 0.0,
        reverse=True,
    )[:3]


def _harvest_context(body: str, hits: list[dict]) -> str:
    chunks = []
    for hit in hits:
        position = hit["position"]
        start = max(0, position - CONTEXT_CHARS)
        end = min(len(body), position + CONTEXT_CHARS)
        snippet = body[start:end].strip()
        chunks.append(f"[keyword: '{hit['keyword']}' | score: {hit['score']:.0f}%]\n{snippet}")

    return "\n\n".join(chunks)


def _classify_email_body(context_snippet: str, subject: str = "") -> EmailBodyClassification:
    subject_section = f"\nEMAIL SUBJECT:\n{subject}\n" if subject else ""
    prompt = f"""You are an email classifier.

Based on the email subject and the extracted email body snippets below, decide if the email is
about a TIMESHEET.

A timesheet email usually mentions hours worked, pay period, dates or days of
the week, clock in/out times, total hours, employee/client/project rows,
approvals, or submitting/reviewing a timesheet.
{subject_section}
SNIPPETS:
{context_snippet}

Reply in exactly this format:
CLASSIFICATION: [TIMESHEET / NOT_A_TIMESHEET]

REASON: [one sentence]
"""

    llm = ChatGroq(
        # model_name="llama-3.3-70b-versatile",
        model_name="llama-3.1-8b-instant",
        temperature=0,
        api_key=settings.GROQ_API_KEY_1,
    )
    structured_llm = llm.with_structured_output(EmailBodyClassificationResponse)
    response = structured_llm.invoke([HumanMessage(content=prompt)])

    if not isinstance(response, EmailBodyClassificationResponse):
        raise ValueError("Invalid email body classification response type")

    return response.classification


def _attachment_is_timesheet(attachment: AttachmentState) -> bool:
    return bool(
        attachment.get("is_timesheet")
        or attachment.get("status") == AttachmentStatus.TIMESHEET.value
    )


async def _update_email_classification_status(
    state: TimeguardState,
    config: RunnableConfig,
    is_timesheet: bool,
) -> None:
    email_id = state.get("email_id")
    if email_id is None:
        logger.warning("Skipping email classification update because email_id is missing")
        return

    db_session = get_db_session(config)
    email_repository = EmailRepository(db_session)
    email = await email_repository.get_by_id(email_id)
    if email is None:
        logger.warning("Email %s not found for classification update", email_id)
        return

    await email_repository.set_status(email, EmailStatus.CLASSIFYED)
    if not is_timesheet:
        await email_repository.set_classification_status(
            email,
            EmailClassificationStatus.NOT_TIMESHEET,
        )
    else:
        await email_repository.set_classification_status(
            email,
            EmailClassificationStatus.TIMESHEET,
        )
    await db_session.commit()
    logger.info(
        "Updated email %s classification to %s",
        email_id,
        "TIMESHEET" if is_timesheet else "NOT_TIMESHEET",
    )


async def _create_content_extract_records(
    state: TimeguardState,
    config: RunnableConfig,
    *,
    body_is_timesheet: bool,
    attachments: list[AttachmentState],
    should_create_records: bool,
) -> tuple[
    UUID | None,
    list[AttachmentState],
]:
    if not should_create_records:
        return None, attachments

    email_id = state.get("email_id")
    if email_id is None:
        logger.warning("Skipping content extract record creation because email_id is missing")
        return None, attachments

    body_content_extract_id = state.get("email_body_content_extract_id")
    updated_attachments: list[AttachmentState] = []
    attachment_content_extract_count = 0
    content_extract_repository = ContentExtractRepository(get_db_session(config))

    timesheet_attachment_ids: list[UUID] = []
    for attachment in attachments:
        if not _attachment_is_timesheet(attachment):
            updated_attachments.append(attachment)
            continue

        attachment_db_id = attachment.get("attachment_db_id")
        if attachment_db_id is None:
            logger.warning(
                "Skipping content extract attachment record"
                " because attachment_db_id is missing for file %s",
                attachment.get("file_name", "<unknown>"),
            )
            updated_attachments.append(attachment)
            continue

        timesheet_attachment_ids.append(attachment_db_id)

    created_records = await content_extract_repository.create_for_classified_sources(
        email_id=email_id,
        body_is_timesheet=body_is_timesheet,
        timesheet_attachment_ids=timesheet_attachment_ids,
    )

    # Map attachment IDs to content_extract_ids
    attachment_id_to_content_extract_id: dict[UUID, UUID] = {}
    for record in created_records:
        if record.attachment_id is not None:
            attachment_id_to_content_extract_id[record.attachment_id] = (
                record.content_extract_id
            )
        elif record.source_type == "body":
            body_content_extract_id = record.content_extract_id

    for attachment in attachments:
        if not _attachment_is_timesheet(attachment):
            updated_attachments.append(attachment)
            continue

        attachment_db_id = attachment.get("attachment_db_id")
        if attachment_db_id is None:
            updated_attachments.append(attachment)
            continue

        content_extract_id = attachment_id_to_content_extract_id.get(attachment_db_id)
        if content_extract_id is None:
            logger.warning(
                "No content_extract_id found for attachment %s",
                attachment.get("file_name", "<unknown>"),
            )
            updated_attachments.append(attachment)
            continue

        updated_attachments.append(
            AttachmentState(
                **{
                    **attachment,
                    "content_extract_id": content_extract_id,
                }
            )
        )
        attachment_content_extract_count += 1

    db_session = get_db_session(config)
    await db_session.commit()
    logger.info(
        "Created or reused %d attachment content extract record(s) for email %s",
        attachment_content_extract_count,
        email_id,
    )
    return body_content_extract_id, updated_attachments


async def email_body_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    body = state.get("body", "")
    body_text = body.strip()
    subject = state.get("subject", "")
    attachments = list(state.get("attachments", []))
    classification = EmailBodyClassification.NOT_A_TIMESHEET
    anchor_hits: list[dict] = []
    context_snippet = ""
    llm_failed = False

    try:
        if not body_text:
            logger.info("Skipping email body classification because body is empty")
        elif len(body_text) < SHORT_BODY_CHAR_THRESHOLD:
            logger.info(
                "Email body is short (%d chars); classifying directly with LLM",
                len(body_text),
            )
            classification = _classify_email_body(body_text, subject)
            context_snippet = body_text
        else:
            anchor_hits = _fuzzy_match_anchors(body, subject)
            if not anchor_hits:
                logger.info("No timesheet anchors found in email body")
            else:
                context_snippet = _harvest_context(body, anchor_hits)
                classification = _classify_email_body(context_snippet, subject)
        logger.info(f"classification result for email body: {classification}")
    except Exception as e:
        logger.exception("LLM classification failed for email body: %s", e)
        llm_failed = True
        classification = EmailBodyClassification.NOT_A_TIMESHEET

        # Set email status to FAILED
        email_id = state.get("email_id")
        if email_id:
            db_session = get_db_session(config)
            email_repository = EmailRepository(db_session)
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="email_body_classification",
                    failure_reason=str(e),
                )
                await db_session.commit()
                logger.info("Set email %s status to FAILED due to LLM error", email_id)
                raise e
    should_mark_email_timesheet = classification == EmailBodyClassification.TIMESHEET or any(
        _attachment_is_timesheet(attachment) for attachment in attachments
    )

    # Only update classification status if LLM didn't fail
    if not llm_failed:
        await _update_email_classification_status(
            state,
            config,
            should_mark_email_timesheet,
        )

    # Create body content_extract if any attachment is timesheet, or if no attachments and
    #  body is timesheet
    has_timesheet_attachments = any(_attachment_is_timesheet(a) for a in attachments)
    should_create_body_extract = (
        has_timesheet_attachments or not attachments
    ) and not llm_failed
    body_is_timesheet_for_extract = (
        classification == EmailBodyClassification.TIMESHEET
        if not has_timesheet_attachments
        else True
    )

    email_body_content_extract_id, updated_attachments = await _create_content_extract_records(
        state,
        config,
        body_is_timesheet=body_is_timesheet_for_extract,
        attachments=attachments,
        should_create_records=should_create_body_extract,
    )

    result = {
        **state,
        "email_body_anchor_hits": anchor_hits,
        "email_body_context": context_snippet,
        "email_body_classification": classification.value,
        "is_timesheet": should_mark_email_timesheet,
        "attachments": updated_attachments,
        "current_attachment_index": 0,
    }
    if email_body_content_extract_id is not None:
        result["email_body_content_extract_id"] = email_body_content_extract_id
    return cast(TimeguardState, result)
