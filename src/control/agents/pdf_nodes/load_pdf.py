# from typing import TypedDict, NotRequired
import pdfplumber

from src.control.agents.state import PDFClassifierState


def load_pdf(state: PDFClassifierState) -> PDFClassifierState:
    with pdfplumber.open(state["pdf_path"]) as pdf:
        total_pages = len(pdf.pages)

    return {
        **state,
        "page_queue": list(range(total_pages)),
        "pages_checked": 0,
        "pdf_classification": "PENDING",
        "pdf_reason": "",
        "current_page": None,
        "anchor_hits": [],
        "context_snippet": "",
    }
