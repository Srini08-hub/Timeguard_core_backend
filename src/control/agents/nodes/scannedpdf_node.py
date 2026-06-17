import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scannedpdfnode(state: TimeguardState) -> TimeguardState:
    logger.info("Routing scanned PDF attachment")
    return state
