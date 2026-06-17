import logging

from src.control.agents.graph import build_email_graph
from src.core.services.gmail_service import GmailService
from src.data.clients.sync_postgress_client import SessionLocal
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="classify_email")
def classify_email(gmail_message_id: str) -> dict:
    logger.info("Task classify_email started for %s", gmail_message_id)
    try:
        # Create a new DB session and Gmail service for this task
        with SessionLocal() as db:
            gmail_service = GmailService()
            graph = build_email_graph(db=db, gmail_service=gmail_service)
            result = graph.invoke({"gmail_message_id": gmail_message_id})
            db.commit()
        return {
            "email_id": result["email_id"],
            "gmail_message_id": gmail_message_id,
        }
    except Exception:
        logger.exception("Classification failed for %s", gmail_message_id)
        raise
