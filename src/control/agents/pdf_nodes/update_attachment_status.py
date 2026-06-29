"""Node to update attachment status after PDF classification."""

import logging

from langchain_core.runnables import RunnableConfig

from src.control.agents.graph_config import get_db_session
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus
from src.data.repositories.attachment_repository import AttachmentRepository

logger = logging.getLogger(__name__)


def _attachment_status_from_classification(
    classification: str | None,
) -> AttachmentStatus:
    if classification == "TIMESHEET":
        return AttachmentStatus.TIMESHEET

    return AttachmentStatus.NOT_TIMESHEET


async def update_pdf_attachment_status(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    """Update attachment status based on PDF classification result."""
    db_session = get_db_session(config)
    attachment_repository = AttachmentRepository(db_session)

    classification = state.get("pdf_classification")
    attachment_status = _attachment_status_from_classification(classification)

    current_index = state.get("current_attachment_index", 0)
    attachments = list(state.get("attachments", []))

    if current_index >= len(attachments):
        logger.warning("Attachment index %d out of range for status update", current_index)
        return state

    attachment_state = attachments[current_index]
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
                "Updated attachment %s to status %s based on PDF classification %s",
                attachment_db_id,
                attachment_status,
                classification,
            )
        else:
            logger.warning("Attachment %s not found for status update", attachment_db_id)

    # Update attachment state with is_timesheet flag
    attachments[current_index] = AttachmentState(
        **{
            **attachment_state,
            "is_timesheet": classification == "TIMESHEET",
        }
    )

    return {
        **state,
        "attachments": attachments,
    }
