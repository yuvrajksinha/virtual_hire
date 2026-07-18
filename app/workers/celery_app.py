"""Celery application: the async task queue backbone every worker epic
(E6 parsing, E7 embedding, E9/E10/E16-E20 crew/verdict tasks, E11
notifications) builds on. See docs/07-technical-stack.md's Celery+Redis
row and docs/06-architecture.md's sync/async boundary table.

VHIRE-13 (E5). Local dev entrypoint: `celery -A app.workers.celery_app worker --loglevel=info`.
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("sift", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Queues per worker type, matching the "separate Fargate task
    # definitions per worker type" decision in docs/07-technical-stack.md.
    task_routes={
        "app.workers.tasks.parsing.*": {"queue": "parsing"},
        "app.workers.tasks.embedding.*": {"queue": "embedding"},
        "app.workers.tasks.verdicts.*": {"queue": "crew"},
    },
    task_default_queue="default",
    # LLM-call-bound tasks are treated as one retryable unit for v1, per
    # EPIC.md's E5 definition of done - default retry/backoff convention
    # every task in app.workers.tasks applies via BaseTask below.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

celery_app.autodiscover_tasks(["app.workers.tasks"])
