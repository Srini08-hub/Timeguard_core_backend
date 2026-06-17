import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def hybridpdfnode(state: TimeguardState) -> TimeguardState:
    logger.info("Routing hybrid PDF attachment")
    return state
