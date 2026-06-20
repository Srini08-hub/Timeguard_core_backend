import logging

from src.config.settings import settings
from src.control.agents.graph import get_email_graph
from src.control.agents.graph_config import (
    DB_SESSION_CONFIG_KEY,
    GMAIL_SERVICE_CONFIG_KEY,
)
from src.core.services.gmail_service import GmailService
from src.data.clients import postgress_client
from src.workers.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)

logger.info(settings.LANGSMITH_PROJECT)


async def _classify_email_async(gmail_message_id: str) -> dict:
    if postgress_client.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized")

    gmail_service = GmailService()
    graph = get_email_graph()

    async with postgress_client.SessionLocal() as db:
        try:
            result = await graph.ainvoke(
                {"gmail_message_id": gmail_message_id},
                config={
                    "configurable": {
                        DB_SESSION_CONFIG_KEY: db,
                        GMAIL_SERVICE_CONFIG_KEY: gmail_service,
                    }
                },
            )
            # await db.commit()
        except Exception:
            await db.rollback()
            raise

    return {
        "email_id": result["email_id"],
        "gmail_message_id": gmail_message_id,
    }


@celery_app.task(name="classify_email")
def classify_email(gmail_message_id: str) -> dict:
    logger.info("Task classify_email started for %s", gmail_message_id)
    try:
        return run_async(_classify_email_async(gmail_message_id))
    except Exception:
        logger.exception("Classification failed for %s", gmail_message_id)
        raise
