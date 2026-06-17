import openpyxl

from src.control.agents.state import ExcelClassifierState


def next_sheet(state: ExcelClassifierState) -> ExcelClassifierState:
    """
    Load exactly ONE sheet on demand, then close the workbook.
    Extracts cell values row by row for that sheet only.
    """
    queue = state["sheet_queue"]

    if not queue:
        return {**state, "current_sheet": None}  # signals graph to stop

    idx = queue[0]
    sheet_name = state["sheet_names"][idx]

    wb = openpyxl.load_workbook(state["file_path"], read_only=True, data_only=True)
    ws = wb[sheet_name]

    rows = []
    combined = ""

    for row in ws.iter_rows(values_only=True):
        # Filter out completely empty rows
        clean_row = [str(cell).strip() for cell in row if cell is not None]
        if not clean_row:
            continue
        row_text = " | ".join(clean_row)
        rows.append(clean_row)
        combined += " " + row_text

    # Check if sheet is hidden
    is_hidden = ws.sheet_state == "hidden" if hasattr(ws, "sheet_state") else False

    wb.close()

    return {
        **state,
        "current_sheet": {
            "sheet_name": sheet_name,
            "sheet_idx": idx,
            "rows": rows,  # list of row lists
            "combined": combined.strip().lower(),
            "is_hidden": is_hidden,
        },
        "sheet_queue": queue[1:],
        "anchor_hits": [],
        "context_snippet": "",
    }
