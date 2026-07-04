# from typing import TypedDict, NotRequired
import pdfplumber

from src.control.agents.state import AttachmentState, TimeguardState


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


def pdf_node(state: TimeguardState) -> TimeguardState:
    attachment_state = _current_attachment(state)
    pdf_path = attachment_state.get("file_path")
    with pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)
        # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    return {
        **state,
        "pdf_page_queue": list(range(total_pages)),
        "pdf_classification": "NOT_A_TIMESHEET",
        "pdf_pages_checked": 0,
        "pdf_current_page": None,
        "pdf_anchor_hits": [],
        "pdf_context_snippet": "",
    }
