import fitz

from src.control.agents.state import AttachmentState, TimeguardState
from src.utils.storage import resolve_attachment_to_local_path


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for scanned PDF processing")

    return attachments[index]


def scanned_pdf_node(state: TimeguardState) -> TimeguardState:
    attachment_state = _current_attachment(state)
    scanned_pdf_path = resolve_attachment_to_local_path(attachment_state)
    doc = fitz.open(scanned_pdf_path)
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    next_state: TimeguardState = {
        **state,
        "scanned_pdf_page_queue": list(range(total_pages)),
        "scanned_pdf_current_page": None,
        "scanned_pdf_classification": "NOT_A_TIMESHEET",
    }
    # if total_pages == 0:
    #     next_state["scanned_pdf_classification"] = "NOT_A_TIMESHEET"
    # elif state.get("scanned_pdf_classification"):
    #     next_state["scanned_pdf_classification"] = state["scanned_pdf_classification"]

    return next_state
