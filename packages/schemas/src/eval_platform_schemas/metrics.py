"""Metric definition and aggregate result schemas."""

from __future__ import annotations

from typing import Any

from eval_platform_schemas.common import StrictModel


class MetricDefinitionRead(StrictModel):
    """Complete public metric plugin declaration."""

    identifier: str
    name: str
    version: str
    description: str
    task_types: list[str]
    required_fields: list[str]
    output_schema: dict[str, Any]
    direction: str
    minimum: float | None
    maximum: float | None
    reference_required: bool
    external_model_required: bool
    determinism: str
    aggregation: str
    failure_behavior: str
    configuration_schema: dict[str, Any]
    computational_cost: str
    monetary_cost: str


class MetricAggregateRead(StrictModel):
    """Aggregate value with a complete denominator partition."""

    metric_identifier: str
    metric_version: str
    value: float | None
    total_count: int
    available_count: int
    missing_count: int
    failed_count: int
    pending_count: int
