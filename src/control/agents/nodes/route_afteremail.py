import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def increment_extraction_node(state: TimeguardState) -> dict[str, int]:
    return {"current_attachment_index": state.get("current_attachment_index", 0) + 1}


def route_after_email_body(state: TimeguardState) -> str:
    # Check whether the email is a timesheet using the state variable `is_timesheet`.
    # If it is not a timesheet, end the graph.
    if not state.get("is_timesheet", False):
        return "end"

    # Get the attachments list.
    attachments = state.get("attachments", [])

    # If the attachment is not present, route to email_extraction_node.
    if not attachments:
        if state.get("email_body_classification") == "TIMESHEET":
            return "email_body_extraction_node"
        return "end"
    # and not state.get("email_body_extraction_done")

    # Loop over the attachments to check if the attachment is timesheet
    # and route based on the attachment type.
    index = state.get("current_attachment_index", 0)
    if index >= len(attachments):
        if state.get("email_body_classification") == "TIMESHEET":
            return "email_body_extraction_node"
        return "end"
    #    and not state.get("email_body_extraction_done")
    attachment = attachments[index]
    is_att_timesheet = (
        attachment.get("is_timesheet") or attachment.get("status") == "TIMESHEET"
    )

    if not is_att_timesheet:
        # Skip this attachment by routing to increment_extraction_node
        return "increment_extraction_node"

    doc_type = attachment.get("doc_type")
    if doc_type is not None and doc_type in ("digital_pdf",):
        return "digital_pdf_extraction_node"
    elif doc_type == "scanned_pdf":
        return "scanned_pdf_extraction_node"
    elif doc_type == "image":
        return "image_extraction_node"
    elif doc_type == "excel":
        return "excel_extraction_node"

    logger.warning(
        "Unsupported doc_type %r for timesheet attachment at index %d", doc_type, index
    )
    return "increment_extraction_node"
