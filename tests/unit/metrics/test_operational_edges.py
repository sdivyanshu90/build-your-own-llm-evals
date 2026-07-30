"""Operational metric value, missingness, and invalid-denominator behavior."""

from __future__ import annotations

import pytest
from eval_platform_metrics.base import MetricContext, ScoreDirection, TaskType
from eval_platform_metrics.operational import OperationalMetric, error_rate, throughput


def test_operational_metric_distinguishes_missing_from_observed_zero() -> None:
    metric = OperationalMetric(
        "operations/test-latency",
        "Latency",
        "latency_ms",
        ScoreDirection.LOWER_IS_BETTER,
        "ms",
    )
    missing = metric.evaluate(
        MetricContext(task_type=TaskType.GENERATION, prediction="", operational={})
    )
    zero = metric.evaluate(
        MetricContext(
            task_type=TaskType.GENERATION,
            prediction="",
            operational={"latency_ms": 0, "latency_ms_estimated": True},
        )
    )
    assert missing.missing and missing.scalar is None
    assert zero.scalar == 0
    assert zero.metadata["estimated"] is True
    assert metric.definition.maximum is None


@pytest.mark.parametrize(
    ("tokens", "seconds"),
    [(-1, 1), (1, -1)],
)
def test_throughput_rejects_negative_inputs(tokens: int, seconds: float) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        throughput(tokens, seconds)
    assert throughput(0, 0) is None


@pytest.mark.parametrize(
    ("failed", "total"),
    [(-1, 1), (2, 1), (0, -1)],
)
def test_error_rate_validates_denominators(failed: int, total: int) -> None:
    with pytest.raises(ValueError, match="invalid failure counts"):
        error_rate(failed, total)
    assert error_rate(0, 0) is None
