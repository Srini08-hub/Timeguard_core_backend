import openpyxl

from src.control.agents.state import AttachmentState, TimeguardState
from src.utils.storage import resolve_attachment_to_local_path


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


def next_sheet(state: TimeguardState) -> TimeguardState:
    """
    Load exactly ONE sheet on demand, then close the workbook.
    Extracts cell values row by row for that sheet only.
    """
    attachment_state = _current_attachment(state)
    excel_path = resolve_attachment_to_local_path(attachment_state)
    queue = state["excel_sheet_queue"]

    if not queue:
        return {**state, "excel_current_sheet": None}  # signals graph to stop

    idx = queue[0]
    sheet_name = state["excel_sheet_names"][idx]

    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb[sheet_name]

    # rows = []
    combined = ""

    for row in ws.iter_rows(values_only=True):
        # Filter out completely empty rows
        clean_row = [str(cell).strip() for cell in row if cell is not None]
        if not clean_row:
            continue
        row_text = "  ".join(clean_row)
        # rows.append(clean_row)
        combined += " " + row_text

    # Check if sheet is hidden
    is_hidden = ws.sheet_state == "hidden" if hasattr(ws, "sheet_state") else False

    wb.close()

    return {
        **state,
        "excel_current_sheet": {
            "sheet_name": sheet_name,
            # "sheet_idx": idx,
            # "rows": rows,  # list of row lists
            "combined": combined.strip().lower(),
            "is_hidden": is_hidden,
        },
        "excel_sheet_queue": queue[1:],
        "excel_anchor_hits": [],
        "excel_context_snippet": "",
    }
