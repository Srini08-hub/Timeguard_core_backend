import fitz

from src.control.agents.state import TimeguardState


def load_pages(state: TimeguardState) -> TimeguardState:
    doc = fitz.open(state["scanned_pdf_file_path"])
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    next_state: TimeguardState = {
        **state,
        "scanned_pdf_page_queue": list(range(total_pages)),
        "scanned_pdf_pages_checked": 0,
        "scanned_pdf_current_page": None,
        "scanned_pdf_classification": "NOT_A_TIMESHEET",
        "scanned_pdf_confidence": 0.0,
        "scanned_pdf_reason": "",
    }
    # if total_pages == 0:
    #     next_state["scanned_pdf_classification"] = "NOT_A_TIMESHEET"
    # elif state.get("scanned_pdf_classification"):
    #     next_state["scanned_pdf_classification"] = state["scanned_pdf_classification"]

    return next_state
