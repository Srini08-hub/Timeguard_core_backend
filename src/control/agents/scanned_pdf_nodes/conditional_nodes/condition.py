from src.control.agents.state import TimeguardState

# def route_after_next_page(state: TimeguardState) -> str:
#     if state.get("scanned_pdf_current_page") is None:
#         return "done"

#     return "scanned_call_vision_llm"


def route_after_vision_llm(state: TimeguardState) -> str:
    if state.get("scanned_pdf_classification") == "TIMESHEET":
        return "done"

    if state.get("scanned_pdf_page_queue"):
        return "scanned_next_page"

    return "done"
