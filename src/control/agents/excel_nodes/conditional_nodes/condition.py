from src.control.agents.state import ExcelClassifierState


def route_sheet_has_content(state: ExcelClassifierState) -> str:
    """
    Mirrors route_page_has_content from the PDF subgraph.
    Called after next_sheet — handles both exit conditions:
      - no current sheet (queue exhausted) → done via next_sheet loop back to END
      - hidden or empty sheet              → skip, loop to next_sheet
      - has content                        → proceed to fuzzy match
    """
    sheet = state["current_sheet"]

    # Queue exhausted — next_sheet set current_sheet to None
    if sheet is None:
        return "done"  # handled below via call_llm route

    if sheet.get("is_hidden"):
        return "next_sheet"

    if len(sheet.get("combined", "").split()) < 8:
        return "next_sheet"

    return "fuzzy_match_anchors"


def route_anchor_found(state: ExcelClassifierState) -> str:
    return "harvest_context" if state["anchor_hits"] else "next_sheet"


def route_after_llm(state: ExcelClassifierState) -> str:
    print("STATE:", state)
    print("CLASSIFICATION:", state["excel_classification"])
    if state["excel_classification"] == "TIMESHEET":
        return "done"
    elif state["sheet_queue"]:
        return "next_sheet"
    else:
        return "done"
