from __future__ import annotations

import logging

from langchain_core.runnables import RunnableConfig

from src.control.agents.state import TimeguardState

logger = logging.getLogger(__name__)


async def matching_prerequisite_node(
    state: TimeguardState,
    config: RunnableConfig,
) -> TimeguardState:
    """Keep the graph edge stable; matching exceptions are emitted in validation."""
    _ = config
    payload = state.get("payload")
    if not isinstance(payload, dict):
        logger.warning("Skipping matching prerequisite check because payload is missing")
    return state
