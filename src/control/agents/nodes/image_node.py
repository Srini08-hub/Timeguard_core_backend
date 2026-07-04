import base64
import logging
import mimetypes
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from src.config.settings import settings
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus
from src.data.models.email import EmailStatus
from src.data.repositories.attachment_repository import AttachmentRepository
from src.data.repositories.email_repository import EmailRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
}


class ImageTimesheetClassification(BaseModel):
    is_timesheet: bool = Field(description="Whether the attached image is a timesheet.")
    # confidence: float = Field(
    #     ge=0.0,
    #     le=1.0,
    #     description="Model confidence from 0.0 to 1.0.",
    # )
    # reasoning: str = Field(
    #     min_length=1,
    #     description="Short rationale based only on visible image evidence.",
    # )


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)
    return attachments[index]


# def _resolve_attachment_path(attachment: AttachmentState) -> Path:
#     attachment_url = attachment.get("attachment_url")
#     if attachment_url:
#         parsed_url = urlparse(attachment_url)
#         candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
#         if candidate.exists():
#             return candidate

#     raise FileNotFoundError(
#         f"Unable to resolve a stored file for attachment {attachment.get('file_name', '')}"
#     )


def _load_image_for_llm(image_path: Path) -> tuple[str, bytes]:
    if not image_path.is_file():
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    media_type, _ = mimetypes.guess_type(image_path.name)
    return (media_type or "application/octet-stream", image_path.read_bytes())


def _classification_status(is_timesheet: bool) -> AttachmentStatus:
    if is_timesheet:
        return AttachmentStatus.TIMESHEET

    return AttachmentStatus.NOT_TIMESHEET


def _classify_image(
    *,
    media_type: str,
    image_bytes: bytes,
) -> ImageTimesheetClassification:
    image_base64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = """Classify the attached image as a timesheet or not.

A timesheet usually contains visible evidence such as employee names or IDs,
dates or pay periods, days of the week, clock in/out times, hours worked,
total hours, client/project rows, approvals, or signatures.

Base the answer only on the image. If the image is unreadable or lacks enough
timesheet evidence, classify it as not a timesheet """

    llm = ChatGoogleGenerativeAI(
        # model="gemini-2.5-flash",
        model="gemini-2.5-flash-lite",
        temperature=0,
        api_key=settings.GOOGLE_API_KEY,
    )
    structured_llm = llm.with_structured_output(ImageTimesheetClassification)
    response = structured_llm.invoke(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{image_base64}"},
                    },
                ]
            )
        ]
    )

    if not isinstance(response, ImageTimesheetClassification):
        raise ValueError("Invalid image classification response type")

    return response


async def image_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    db_session = get_db_session(config)
    attachment_repository = AttachmentRepository(db_session)
    email_repository = EmailRepository(db_session)

    attachment_state = _current_attachment(state)
    image_path = attachment_state.get("file_path")
    # image_path = _resolve_attachment_path(attachment_state)
    media_type, image_bytes = _load_image_for_llm(image_path)

    logger.info(
        "Classifying image attachment %s from %s",
        attachment_state.get("file_name", ""),
        image_path,
    )

    classification = None
    llm_failed = False

    try:
        classification = _classify_image(
            media_type=media_type,
            image_bytes=image_bytes,
        )
        attachment_status = _classification_status(classification.is_timesheet)
    except Exception as e:
        logger.exception("Image classification failed: %s", e)
        llm_failed = True
        attachment_status = AttachmentStatus.NOT_TIMESHEET
        failure_reason = str(e)

        email_id = state.get("email_id")
        if email_id:
            email = await email_repository.get_by_id(email_id)
            if email:
                await email_repository.set_status(
                    email,
                    EmailStatus.FAILED,
                    failure_stage="image_classification",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set email %s status to FAILED due to image classification error", email_id
                )

        attachment_db_id = attachment_state.get("attachment_db_id")
        if attachment_db_id:
            attachment = await attachment_repository.get_by_id(attachment_db_id)
            if attachment is not None:
                await attachment_repository.set_failed(
                    attachment,
                    failure_stage="image_classification",
                    failure_reason=failure_reason,
                )
                logger.info(
                    "Set attachment %s status to FAILED due to image classification error",
                    attachment_db_id,
                )
            else:
                logger.warning(
                    "Attachment %s not found for image failure update",
                    attachment_db_id,
                )

        await db_session.commit()
        raise

    # Only update attachment status if LLM didn't fail
    if not llm_failed:
        attachment_db_id = attachment_state.get("attachment_db_id")
        if attachment_db_id:
            attachment = await attachment_repository.get_by_id(attachment_db_id)
            if attachment is not None:
                await attachment_repository.set_status(
                    attachment,
                    status=attachment_status,
                )
                await db_session.commit()
                logger.info(
                    "Updated attachment %s to status %s",
                    attachment_db_id,
                    attachment_status,
                )
            else:
                logger.warning(
                    "Attachment %s not found for status update",
                    attachment_db_id,
                )

    current_index = state.get("current_attachment_index", 0)
    attachments = list(state.get("attachments", []))
    updated_attachment = AttachmentState(
        **{
            **attachment_state,
            "is_timesheet": classification.is_timesheet if classification else False,
        }
    )
    attachments[current_index] = updated_attachment

    return {
        **state,
        "attachments": attachments,
    }
