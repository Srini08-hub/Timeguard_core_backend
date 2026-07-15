import logging
from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from src.control.agents.graph_config import get_db_session
from src.control.agents.llm_key_rotation import invoke_groq_structured_with_key_rotation
from src.control.agents.state import TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository

logger = logging.getLogger(__name__)


async def _mark_pdf_llm_failed(
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
                failure_stage="pdf_llm_classification",
                failure_reason=failure_reason,
            )
            logger.info(
                "Set email %s status to FAILED due to PDF LLM classification error",
                email_id,
            )
        else:
            logger.warning("Email %s not found for PDF LLM failure update", email_id)

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
                    failure_stage="pdf_llm_classification",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to PDF LLM classification error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for PDF LLM failure update",
                    attachment_db_id,
                )

    await db_session.commit()


class PDFClassification(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class PDFClassificationResponse(BaseModel):
    classification: PDFClassification = Field(
        description="Whether the  PDF page is a timesheet."
    )
    # confidence: float = Field(
    #     ge=0.0,
    #     le=1.0,
    #     description="Model confidence from 0.0 to 1.0.",
    # )
    # reason: str = Field(
    #     min_length=1,
    #     description="Short rationale based only on visible page evidence.",
    # )
    # reason: str = Field(description="Short explanation for the classification")


async def call_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    prompt = f"""You are a document classifier.

Based ONLY on the extracted snippets below, decide if this page is from a TIMESHEET.

A timesheet has: employee name/ID, dates or days of week, hours worked/in/out,
total hours, pay period, or approval signatures.

SNIPPETS:
{state["pdf_context_snippet"]}

Reply in exactly this format:
CLASSIFICATION: [TIMESHEET / NOT_A_TIMESHEET]

"""

    try:
        response = invoke_groq_structured_with_key_rotation(
            model_name="llama-3.1-8b-instant",
            output_schema=PDFClassificationResponse,
            messages=[HumanMessage(content=prompt)],
            preferred_key_name="GROQ_API_KEY_1",
            operation_name="PDF LLM classification",
        )

        if not isinstance(response, PDFClassificationResponse):
            raise ValueError("Invalid LLM response type")

        return {
            **state,
            "pdf_classification": response.classification.value,
            # "pdf_reason": response.reason,
        }
    except Exception as exc:
        logger.exception("PDF LLM classification failed: %s", exc)
        await _mark_pdf_llm_failed(state, config, str(exc))
        raise
