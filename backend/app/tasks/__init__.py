"""
Celery application configuration for CRM background tasks.
"""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "crm_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.send_campaign"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Chicago",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Rate limiting
    task_default_rate_limit="10/m",
    # Result expiration (24 hours)
    result_expires=86400,
)
