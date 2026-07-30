"""Latency, token, throughput, cost, refusal, and error metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eval_platform_metrics.base import (
    EMPTY_CONFIG_SCHEMA,
    RESULT_SCHEMA,
    Determinism,
    FailureBehavior,
    MetricContext,
    MetricDefinition,
    MetricResult,
    ScoreDirection,
    TaskType,
)


@dataclass(frozen=True, slots=True)
class OperationalMetric:
    """Read one explicitly named operational value from a sample trace."""

    identifier: str
    name: str
    field: str
    direction: ScoreDirection
    unit: str
    minimum: float = 0

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier=self.identifier,
            name=self.name,
            version="1.0.0",
            description=f"Recorded per-sample {self.name.lower()} in {self.unit}.",
            task_types=frozenset(TaskType),
            required_fields=frozenset({"operational"}),
            output_schema=RESULT_SCHEMA,
            direction=self.direction,
            minimum=self.minimum,
            maximum=None,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean_and_quantiles",
            failure_behavior=FailureBehavior.RETURN_MISSING,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(1)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        raw = context.operational.get(self.field)
        if raw is None:
            return MetricResult(
                self.identifier,
                "1.0.0",
                missing=True,
                explanation=f"{self.name} was not observed.",
                metadata={"unit": self.unit},
            )
        return MetricResult(
            self.identifier,
            "1.0.0",
            scalar=float(raw),
            metadata={
                "unit": self.unit,
                "estimated": bool(context.operational.get(f"{self.field}_estimated", False)),
            },
        )


def throughput(output_tokens: int, generation_seconds: float) -> float | None:
    """Output tokens divided by generation duration."""

    if output_tokens < 0 or generation_seconds < 0:
        raise ValueError("throughput inputs must be non-negative")
    return output_tokens / generation_seconds if generation_seconds else None


def error_rate(failed: int, total: int) -> float | None:
    """Failures divided by all attempted samples."""

    if failed < 0 or total < 0 or failed > total:
        raise ValueError("invalid failure counts")
    return failed / total if total else None
