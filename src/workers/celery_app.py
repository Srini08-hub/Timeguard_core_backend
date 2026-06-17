from celery import Celery

from src.config.settings import settings

celery_app = Celery(
    "core_backend",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    accept_content=["json"],
    enable_utc=True,
    result_serializer="json",
    task_serializer="json",
    timezone="UTC",
)

celery_app.autodiscover_tasks(["src.workers"])
