# from typing import TypedDict, NotRequired
import pdfplumber

from src.control.agents.state import TimeguardState


def load_pdf(state: TimeguardState) -> TimeguardState:
    with pdfplumber.open(state["pdf_file_path"]) as pdf:
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
