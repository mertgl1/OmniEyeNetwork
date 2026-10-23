from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "omnieye_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Example placeholder task for Faz 1 / Faz 3
@celery_app.task(name="app.core.celery_app.ping_task")
def ping_task() -> str:
    return "Celery worker is running healthy!"
