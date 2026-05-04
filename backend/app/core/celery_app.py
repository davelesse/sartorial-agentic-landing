"""
Sartorial Agentic — Celery Configuration
Task queues for agent execution, emails, Stripe sync, analytics.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "sartorial_agentic",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Europe/Paris",
    enable_utc=True,

    # Task routing — each task type gets its own queue
    task_routes={
        "app.agents.tasks.*":  {"queue": "agents"},
        "app.emails.tasks.*":  {"queue": "emails"},
        "app.stripe.tasks.*":  {"queue": "stripe"},
        "app.analytics.tasks.*": {"queue": "analytics"},
    },

    # Concurrency & limits
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=300,       # 5 min hard limit
    task_soft_time_limit=240,  # 4 min soft limit

    # Result backend
    result_expires=3600,  # 1 hour

    # Scheduled tasks (Celery Beat)
    beat_schedule={
        # Daily analytics report at 7:00 AM Paris
        "daily-analytics-report": {
            "task": "app.analytics.tasks.generate_daily_report",
            "schedule": crontab(hour=7, minute=0),
        },
        # Stripe sync every 6 hours
        "stripe-product-sync": {
            "task": "app.stripe.tasks.sync_products",
            "schedule": crontab(hour="*/6", minute=0),
        },
        # Agent health check every 15 minutes
        "agent-health-check": {
            "task": "app.agents.tasks.health_check_all",
            "schedule": crontab(minute="*/15"),
        },
        # Weekly digest email — Monday 9:00 AM
        "weekly-digest": {
            "task": "app.emails.tasks.send_weekly_digest",
            "schedule": crontab(hour=9, minute=0, day_of_week=1),
        },
    },
)

# Auto-discover tasks in app modules
celery_app.autodiscover_tasks([
    "app.agents",
    "app.emails",
    "app.stripe",
    "app.analytics",
])
