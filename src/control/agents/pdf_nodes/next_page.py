import pdfplumber

from src.control.agents.state import TimeguardState


def next_page(state: TimeguardState) -> TimeguardState:
    queue = state["pdf_page_queue"]

    if not queue:
        return {**state, "pdf_current_page": None}

    idx = queue[0]

    with pdfplumber.open(state["pdf_file_path"]) as pdf:
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
        "pdf_current_page": {
            "page_num": idx + 1,
            # "text":     text,
            # "tables":   tables,
            "combined": combined,
        },
        "pdf_page_queue": queue[1:],
        "pdf_anchor_hits": [],
        "pdf_context_snippet": "",
    }
