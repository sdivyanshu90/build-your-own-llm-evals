"""Bounded Celery delivery configuration tests."""

from __future__ import annotations

from eval_platform_infrastructure.settings import Settings
from eval_platform_worker.celery_app import create_celery


def test_outbox_schedule_expires_stale_relay_tasks() -> None:
    application = create_celery(Settings(outbox_relay_interval_seconds=7))
    schedule = application.conf.beat_schedule["relay-outbox"]

    assert schedule["schedule"] == 7
    assert schedule["options"]["expires"] == 14
    assert application.conf.task_acks_late is True
    assert application.conf.worker_prefetch_multiplier == 1
