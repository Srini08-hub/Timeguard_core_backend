import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image_node(state: TimeguardState) -> TimeguardState:
    logger.info("Image attachments are not processed yet")
    return state
