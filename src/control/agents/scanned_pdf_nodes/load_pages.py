import fitz

from src.control.agents.state import ScannedPDFClassifierState


def load_pages(state: ScannedPDFClassifierState) -> ScannedPDFClassifierState:
    doc = fitz.open(state["pdf_path"])
    try:
        total_pages = doc.page_count
    finally:
        doc.close()

    next_state: ScannedPDFClassifierState = {
        **state,
        "page_queue": list(range(total_pages)),
        "pages_checked": 0,
        "current_page": None,
        "scanned_pdf_classification": "NOT_A_TIMESHEET",
        "confidence": 0.0,
        "reason": "",
    }
    # if total_pages == 0:
    #     next_state["scanned_pdf_classification"] = "NOT_A_TIMESHEET"
    # elif state.get("scanned_pdf_classification"):
    #     next_state["scanned_pdf_classification"] = state["scanned_pdf_classification"]

    return next_state
