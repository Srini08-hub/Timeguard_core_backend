from src.control.agents.state import TimeguardState


# def route_pages_remaining(state: TimeguardState) -> str:
#     # if state.get("pdf_classification") in ("TIMESHEET", "NOT_A_TIMESHEET"):
#     #     return "done"
#     return "next_page" if state["pdf_page_queue"] else "done"
# Empty page is considered "done" and will not be processed further.
#  This is to avoid unnecessary processing of empty pages,
#  which are unlikely to contain relevant information for classification.
def route_page_has_content(state: TimeguardState) -> str:
    current_page = state.get("pdf_current_page")
    combined = current_page.get("combined", "") if current_page else ""
    # combined.spilt() returns a list of words in the combined text.
    #  If the length of this list is 8 or more,
    #  it indicates that the page has enough content to be processed further.
    #  Otherwise, it is considered to have insufficient content and will be skipped.
    return "pdf_fuzzy_match_anchors" if len(combined.split()) > 0 else "next_page"


def route_anchor_found(state: TimeguardState) -> str:
    return "pdf_harvest_context" if state.get("pdf_anchor_hits") else "next_page"


def route_after_llm(state: TimeguardState) -> str:
    if state.get("pdf_classification") == "TIMESHEET":
        return "done"
    elif state.get("pdf_page_queue"):
        return "next_page"
    else:
        return "done"
