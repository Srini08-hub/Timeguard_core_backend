from __future__ import annotations

import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def node_collect_results(state: TimeguardState) -> dict:
    """Terminal node â€” results already accumulated via the reducer; this
    is a clean place to log a summary before END."""
    n_ok = sum(1 for r in state["results"] if r["success"])
    n_fail = len(state["results"]) - n_ok
    logger.info("Workflow complete: %d block(s) succeeded, %d failed.", n_ok, n_fail)
    # logger.info("Results: %s", state["results"])
    return {}
