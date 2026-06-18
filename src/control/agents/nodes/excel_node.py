import logging
from pathlib import Path
from urllib.parse import urlparse

from langchain_core.runnables import RunnableConfig

from src.config.settings import settings
from src.control.agents.excel_subgraph import excel_subgraph
from src.control.agents.graph_config import get_db_session
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus
from src.data.repositories.attachment_repository import AttachmentRepository

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


def _resolve_attachment_path(attachment: AttachmentState) -> Path | None:
    attachment_url = attachment.get("attachment_url")
    if attachment_url:
        parsed_url = urlparse(attachment_url)
        candidate = settings.ATTACHMENT_STORAGE_DIR / Path(parsed_url.path).name
        if candidate.exists():
            return candidate

    file_name = attachment.get("file_name")
    if file_name:
        matches = list(settings.ATTACHMENT_STORAGE_DIR.glob(f"*_{file_name}"))
        if matches:
            return matches[0]
    return None


def _attachment_status_from_classification(
    classification: str | None,
) -> AttachmentStatus:
    if classification == "TIMESHEET":
        return AttachmentStatus.TIMESHEET

    return AttachmentStatus.NOT_TIMESHEET


async def excelnode(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    db_session = get_db_session(config)
    attachment_repository = AttachmentRepository(db_session)

    attachment_state = _current_attachment(state)
    excel_path = _resolve_attachment_path(attachment_state)

    logger.info(
        "Processing digital Excel attachment %s from %s",
        attachment_state.get("file_name", ""),
        excel_path,
    )

    excel_state = excel_subgraph.invoke({"file_path": str(excel_path)})
    classification = excel_state.get("excel_classification")
    attachment_status = _attachment_status_from_classification(classification)

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
                "Attachment %s not found for status update", attachment_db_id
            )

    current_index = state.get("current_attachment_index", 0)
    attachments = list(state.get("attachments", []))
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
