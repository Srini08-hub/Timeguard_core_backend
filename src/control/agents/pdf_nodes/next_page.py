import pdfplumber

from src.control.agents.state import PDFClassifierState


def next_page(state: PDFClassifierState) -> PDFClassifierState:
    queue = state["page_queue"]

    if not queue:
        return {**state, "current_page": None}

    idx = queue[0]

    with pdfplumber.open(state["pdf_path"]) as pdf:
        page = pdf.pages[idx]
        text = page.extract_text() or ""
        tables = page.extract_tables() or []

    table_text = ""
    for table in tables:
        for row in table:
            table_text += " " + " ".join(str(c) for c in row if c)

    combined = (text + " " + table_text).strip().lower()

    return {
        **state,
        "current_page": {
            "page_num": idx + 1,
            # "text":     text,
            # "tables":   tables,
            "combined": combined,
        },
        "page_queue": queue[1:],
        "anchor_hits": [],
        "context_snippet": "",
    }
