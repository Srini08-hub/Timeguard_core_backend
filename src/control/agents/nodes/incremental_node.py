from src.control.agents.state import TimeguardState


def increment_attachment_node(state: TimeguardState) -> dict[str, int]:
    return {"current_attachment_index": state.get("current_attachment_index", 0) + 1}
