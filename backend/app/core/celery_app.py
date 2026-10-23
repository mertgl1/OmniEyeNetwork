from celery import Celery
from celery.schedules import crontab
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
    timezone=settings.CELERY_TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    imports=["app.tasks.backup_tasks", "app.tasks.port_discovery_tasks"],
    beat_schedule={
        "nightly-device-configuration-backup": {
            "task": "app.tasks.backup_tasks.dispatch_scheduled_backups",
            "schedule": crontab(hour=3, minute=0),
        },
        "hourly-device-port-discovery": {
            "task": "app.tasks.port_discovery_tasks.dispatch_port_discovery",
            "schedule": crontab(minute=0),
        },
    },
)

# Example placeholder task for Faz 1 / Faz 3
@celery_app.task(name="app.core.celery_app.ping_task")
def ping_task() -> str:
    return "Celery worker is running healthy!"
