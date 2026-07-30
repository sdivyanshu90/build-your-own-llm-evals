"""Celery composition root and durable delivery policy."""

from __future__ import annotations

from celery import Celery
from eval_platform_infrastructure.observability import configure_tracing
from eval_platform_infrastructure.settings import Settings


def create_celery(settings: Settings | None = None) -> Celery:
    """Create a worker configured for at-least-once, late-acknowledged delivery."""

    current = settings or Settings()
    configure_tracing(
        "eval-platform-worker",
        current.service_version,
        current.otlp_endpoint,
    )
    if current.otlp_endpoint:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        CeleryInstrumentor().instrument()  # type: ignore[no-untyped-call]
        HTTPXClientInstrumentor().instrument()
    application = Celery(
        "eval-platform",
        broker=current.celery_broker_url.get_secret_value(),
        include=["eval_platform_worker.tasks"],
    )
    application.conf.update(
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_serializer="json",
        accept_content=["json"],
        result_backend=None,
        task_routes={
            "eval_platform_worker.tasks.execute_run": {"queue": "generation"},
            "eval_platform_worker.tasks.relay_outbox": {"queue": "maintenance"},
        },
        broker_connection_retry_on_startup=True,
        task_soft_time_limit=600,
        task_time_limit=660,
        beat_schedule={
            "relay-outbox": {
                "task": "eval_platform_worker.tasks.relay_outbox",
                "schedule": current.outbox_relay_interval_seconds,
                "options": {
                    "expires": max(10.0, current.outbox_relay_interval_seconds * 2),
                },
            }
        },
    )
    return application


celery_app = create_celery()
