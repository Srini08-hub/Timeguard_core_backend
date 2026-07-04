import logging
from enum import StrEnum

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import TimeguardState
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository

logger = logging.getLogger(__name__)


class ScannedPDFClassification(StrEnum):
    TIMESHEET = "TIMESHEET"
    NOT_A_TIMESHEET = "NOT_A_TIMESHEET"


class ScannedPDFClassificationResponse(BaseModel):
    classification: ScannedPDFClassification = Field(
        description="Whether the scanned PDF page is a timesheet."
    )


async def call_vision_llm(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    current_page = state.get("scanned_pdf_current_page")
    if current_page is None:
        return {**state, "scanned_pdf_classification": "NOT_A_TIMESHEET"}

    prompt = """Classify this scanned PDF page as a timesheet or not.

A timesheet usually contains visible evidence such as employee names or IDs,
dates or pay periods, days of the week, clock in/out times, hours worked,
total hours, client/project rows, approvals, or signatures.

Base the answer only on the page image. If the page is unreadable or lacks
enough timesheet evidence, classify it as not a timesheet"""

    try:
        llm = ChatGoogleGenerativeAI(
            # model="gemini-2.5-flash",
            model="gemini-2.5-flash-lite",
            temperature=0,
            api_key=settings.GOOGLE_API_KEY,
        )
        structured_llm = llm.with_structured_output(ScannedPDFClassificationResponse)
        response = structured_llm.invoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:{current_page['image_media_type']};base64,"
                                    f"{current_page['image_base64']}"
                                )
                            },
                        },
                    ]
                )
            ]
        )

        if not isinstance(response, ScannedPDFClassificationResponse):
            raise ValueError("Invalid scanned PDF classification response type")

        # final_status = state.get("final_status")
        # if response.classification == ScannedPDFClassification.TIMESHEET:
        #     final_status = response.classification.value
        # elif not state.get("scanned_pdf_page_queue"):
        #     final_status = response.classification.value

        next_state: TimeguardState = {
            **state,
            "scanned_pdf_classification": response.classification.value,
            # "scanned_pdf_confidence": response.confidence,
            # "scanned_pdf_reason": response.reason,
        }
        # if final_status is not None:
        #     next_state["final_status"] = final_status

        return next_state
    except Exception as e:
        logger.exception("Scanned PDF vision LLM classification failed: %s", e)
        failure_reason = str(e)
        db_session = get_db_session(config)
        email_repository = EmailRepository(db_session)
        attachment_repository = AttachmentRepository(db_session)

        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="scanned_pdf_vision_classification",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set email %s status to FAILED due to scanned PDF vision LLM error",
                    email_id,
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
                        failure_stage="scanned_pdf_vision_classification",
                        failure_reason=failure_reason,
                    )
                    logger.info(
                        "Set attachment %s status to FAILED due to scanned "
                        "PDF vision LLM error",
                        attachment_db_id,
                    )
                else:
                    logger.warning(
                        "Attachment %s not found for scanned PDF vision failure update",
                        attachment_db_id,
                    )

        await db_session.commit()
        raise
