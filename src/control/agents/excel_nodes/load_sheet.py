import openpyxl

from src.control.agents.state import TimeguardState


def load_workbook_meta(state: TimeguardState) -> TimeguardState:
    """
    Don't read any sheet data yet.
    Just open the workbook to get sheet names, then close it.
    """
    wb = openpyxl.load_workbook(
        state["excel_file_path"],
        read_only=True,  # memory efficient
        data_only=True,
    )  # get values not formulas
    sheet_names = wb.sheetnames
    wb.close()

    return {
        **state,
        "excel_sheet_names": sheet_names,
        "excel_sheet_queue": list(range(len(sheet_names))),
        "excel_classification": "PENDING",
    }
