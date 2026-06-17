import logging
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from src.config.settings import settings
from src.control.agents.pdf_subgraph import pdf_subgraph
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


def _resolve_attachment_path(attachment: AttachmentState) -> Path:
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

    raise FileNotFoundError(
        f"Unable to resolve a stored file for attachment "
        f"{attachment.get('file_name', '')}"
    )


def _attachment_status_from_classification(
    classification: str | None,
) -> AttachmentStatus:
    if classification == "TIMESHEET":
        return AttachmentStatus.TIMESHEET

    return AttachmentStatus.NOT_TIMESHEET
    # return AttachmentStatus.PROCESSED


def build_digitalpdfnode(
    db_session: Session,
) -> Callable[[TimeguardState], TimeguardState]:
    attachment_repository = AttachmentRepository(db_session)

    def digitalpdfnode(state: TimeguardState) -> TimeguardState:
        attachment_state = _current_attachment(state)
        pdf_path = _resolve_attachment_path(attachment_state)

        logger.info(
            "Processing digital PDF attachment %s from %s",
            attachment_state.get("file_name", ""),
            pdf_path,
        )

        pdf_state = pdf_subgraph.invoke({"pdf_path": str(pdf_path)})
        classification = pdf_state.get("pdf_classification")
        attachment_status = _attachment_status_from_classification(classification)

        attachment_db_id = attachment_state.get("attachment_db_id")
        if attachment_db_id:
            attachment = attachment_repository.get_by_id(attachment_db_id)
            # attachment = db_session.get(Attachment, attachment_db_id)
            if attachment is not None:
                attachment_repository.set_status(attachment, status=attachment_status)
                logger.info(
                    "Updated attachment %s to status %s",
                    attachment_db_id,
                    attachment_status,
                )
            else:
                logger.warning(
                    "Attachment %s not found for status update", attachment_db_id
                )

        return state

    return digitalpdfnode
