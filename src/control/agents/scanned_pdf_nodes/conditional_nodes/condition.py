from src.control.agents.state import ScannedPDFClassifierState


def route_after_next_page(state: ScannedPDFClassifierState) -> str:
    if state.get("current_page") is None:
        return "done"

    return "call_vision_llm"


def route_after_vision_llm(state: ScannedPDFClassifierState) -> str:
    if state.get("scanned_pdf_classification") == "TIMESHEET":
        return "done"

    if state.get("page_queue"):
        return "next_page"

    return "done"
