"""
Celery application configuration for CRM background tasks.

Worker startup: celery -A app.tasks.celery_app worker --loglevel=info -Q email,default
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
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_rate_limit="10/m",
    result_expires=86400,
    task_reject_on_worker_lost=True,
    task_default_queue="default",
    task_routes={
        "app.tasks.send_campaign.*": {"queue": "email"},
    },
)
