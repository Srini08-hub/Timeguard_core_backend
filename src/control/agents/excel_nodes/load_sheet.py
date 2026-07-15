import openpyxl

from src.control.agents.state import AttachmentState, TimeguardState
from src.utils.storage import resolve_attachment_to_local_path


def _current_attachment(state: TimeguardState) -> AttachmentState:
    attachments = state.get("attachments", [])
    index = state.get("current_attachment_index", 0)

    if index >= len(attachments):
        raise ValueError("No attachment available for PDF processing")

    return attachments[index]


def excel_node(state: TimeguardState) -> TimeguardState:
    """
    Don't read any sheet data yet.
    Just open the workbook to get sheet names, then close it.
    """
    attachment_state = _current_attachment(state)
    excel_path = resolve_attachment_to_local_path(attachment_state)
    wb = openpyxl.load_workbook(
        excel_path,
        read_only=True,  # memory efficient
        data_only=True,
    )  # get values not formulas
    sheet_names = wb.sheetnames
    wb.close()

    return {
        **state,
        "excel_sheet_names": sheet_names,
        "excel_sheet_queue": list(range(len(sheet_names))),
        "excel_classification": "NOT_A_TIMESHEET",
    }
