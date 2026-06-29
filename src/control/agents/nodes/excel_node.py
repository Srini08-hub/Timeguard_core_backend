import logging
from pathlib import Path
from typing import cast
from urllib.parse import urlparse

from src.config.settings import settings
from src.control.agents.state import AttachmentState, TimeguardState
from src.data.models.attachment import AttachmentStatus

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
    # config: RunnableConfig,
) -> TimeguardState:
    # db_session = get_db_session(config)
    # attachment_repository = AttachmentRepository(db_session)

    attachment_state = _current_attachment(state)
    excel_path = _resolve_attachment_path(attachment_state)

    logger.info(
        "Processing digital Excel attachment %s from %s",
        attachment_state.get("file_name", ""),
        excel_path,
    )

    # Set excel_file_path in state for the integrated excel classification flow
    result = cast(
        TimeguardState,
        {
            **state,
            "excel_file_path": str(excel_path),
        },
    )
    return result
