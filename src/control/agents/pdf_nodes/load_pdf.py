# from typing import TypedDict, NotRequired
import pdfplumber

from src.control.agents.state import PDFClassifierState


def load_pdf(state: PDFClassifierState) -> PDFClassifierState:
    with pdfplumber.open(state["pdf_path"]) as pdf:
        total_pages = len(pdf.pages)
        # [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    return {
        **state,
        "page_queue": list(range(total_pages)),
        "pdf_classification": "NOT_A_TIMESHEET",
        "pages_checked": 0,
        "current_page": None,
        "anchor_hits": [],
        "context_snippet": "",
    }
