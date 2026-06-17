import logging

from src.control.agents.state import TimeguardState

logger = logging.getLogger(__name__)


def classify_attachments_router(state: TimeguardState) -> str:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    # All attachments processed
    if index >= len(attachments):
        return "email_body_node"

    attachment = attachments[index]
    doc_type = attachment.get("doc_type")

    if doc_type == "pdf":
        return "pdf_classifying_node"
    elif doc_type == "image":
        return "image_node"
    elif doc_type == "excel":
        return "excel_node"

    # Skip unsupported attachment
    return "increment_attachment_node"
