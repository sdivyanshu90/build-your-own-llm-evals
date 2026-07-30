"""Deterministic metric and classification aggregation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean

from eval_platform_metrics.base import MetricResult


@dataclass(frozen=True, slots=True)
class Aggregate:
    """Aggregate with explicit total, available, missing, and failed counts."""

    value: float | None
    total_count: int
    available_count: int
    missing_count: int
    failed_count: int


def aggregate_mean(
    results: list[MetricResult],
    *,
    failed_count: int = 0,
) -> Aggregate:
    """Mean finite scalar values without silently dropping missing results."""

    values = [
        result.scalar
        for result in results
        if result.scalar is not None and math.isfinite(result.scalar)
    ]
    missing = len(results) - len(values)
    return Aggregate(
        value=fmean(values) if values else None,
        total_count=len(results) + failed_count,
        available_count=len(values),
        missing_count=missing,
        failed_count=failed_count,
    )
