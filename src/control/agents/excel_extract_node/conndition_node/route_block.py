from src.control.agents.state import TimeguardState


def increment_excel_block(state: TimeguardState) -> dict:
    state["current_excel_block_index"] += 1
    return {**state, "current_excel_block_index": state["current_excel_block_index"]}


def route_next_block(state: TimeguardState) -> str:
    if state["current_excel_block_index"] >= len(state["blocks"]):
        return "collect_results"

    return "extract_block_with_llm"
