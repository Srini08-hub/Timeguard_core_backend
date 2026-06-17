import logging

from src.control.agents.state import TimeguardState

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def email_body_node(state: TimeguardState) -> TimeguardState:
    # logger.info("Reached email body node")
    return state
