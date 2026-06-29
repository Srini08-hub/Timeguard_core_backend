import logging
from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository

logger = logging.getLogger(__name__)


async def _mark_excel_llm_failed(
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
                failure_stage="excel_llm_classification",
                failure_reason=failure_reason,
            )
            logger.info(
                "Set email %s status to FAILED due to Excel LLM classification error",
                email_id,
            )
        else:
            logger.warning("Email %s not found for Excel LLM failure update", email_id)

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
                    failure_stage="excel_llm_classification",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to Excel LLM classification error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for Excel LLM failure update",
                    attachment_db_id,
                )

    await db_session.commit()


class Excelclassifier(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class ExcelClassificationResponse(BaseModel):
    classification: Excelclassifier = Field(
        description="Whether the page belongs to a timesheet"
    )
    reason: str = Field(description="Short explanation for the classification")


async def call_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    prompt = f"""You are a document classifier.

Based ONLY on the extracted snippets below, decide if this page is from a TIMESHEET.

A timesheet has: employee name/ID, dates or days of week, hours worked/in/out,
total hours, pay period, or approval signatures.

SNIPPETS:
{state["excel_context_snippet"]}

Reply in exactly this format:
CLASSIFICATION: [TIMESHEET / NOT_A_TIMESHEET]

REASON: [one sentence]
"""

    try:
        llm = ChatGroq(
            # model_name="llama-3.3-70b-versatile",
            model_name="llama-3.1-8b-instant",
            temperature=0,
            api_key=settings.GROQ_API_KEY,
        )

        structured_llm = llm.with_structured_output(ExcelClassificationResponse)
        response = structured_llm.invoke([HumanMessage(content=prompt)])

        if not isinstance(response, ExcelClassificationResponse):
            raise ValueError("Invalid LLM response type")

        return {**state, "excel_classification": response.classification.value}
    except Exception as exc:
        logger.exception("Excel LLM classification failed: %s", exc)
        await _mark_excel_llm_failed(state, config, str(exc))
        raise
