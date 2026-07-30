"""Metric contracts, typed results, compatibility checks, and failure isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from jsonschema import Draft202012Validator


class TaskType(StrEnum):
    """Task types used for metric compatibility."""

    GENERATION = "generation"
    QA = "qa"
    CLASSIFICATION = "classification"
    SUMMARIZATION = "summarization"
    EXTRACTION = "extraction"
    RAG = "rag"
    AGENT = "agent"
    CONVERSATION = "conversation"


class ScoreDirection(StrEnum):
    """How larger values should be interpreted."""

    HIGHER_IS_BETTER = "higher_is_better"
    LOWER_IS_BETTER = "lower_is_better"
    NEUTRAL = "neutral"


class Determinism(StrEnum):
    """Metric reproducibility properties."""

    DETERMINISTIC = "deterministic"
    SEEDED = "seeded"
    EXTERNAL_MODEL = "external_model"


class FailureBehavior(StrEnum):
    """How a metric failure affects its own result."""

    RECORD_FAILURE = "record_failure"
    RETURN_MISSING = "return_missing"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Complete immutable metric plugin declaration."""

    identifier: str
    name: str
    version: str
    description: str
    task_types: frozenset[TaskType]
    required_fields: frozenset[str]
    output_schema: dict[str, Any]
    direction: ScoreDirection
    minimum: float | None
    maximum: float | None
    reference_required: bool
    external_model_required: bool
    determinism: Determinism
    aggregation: str
    failure_behavior: FailureBehavior
    configuration_schema: dict[str, Any]
    computational_cost: str
    monetary_cost: str

    def __post_init__(self) -> None:
        if not self.identifier or not self.version or not self.name:
            raise ValueError("metric identity fields must not be empty")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("metric score range is inverted")


@dataclass(frozen=True, slots=True)
class MetricContext:
    """Normalized per-sample inputs available to metric plugins."""

    task_type: TaskType
    input: Any = None
    prediction: Any = None
    reference: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieved_items: tuple[dict[str, Any], ...] = ()
    relevant_item_ids: frozenset[str] = frozenset()
    trajectory: tuple[dict[str, Any], ...] = ()
    operational: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MetricResult:
    """One typed per-sample metric result."""

    metric_id: str
    metric_version: str
    scalar: float | None = None
    label: str | None = None
    structured: dict[str, Any] | None = None
    explanation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    missing: bool = False


class Metric(Protocol):
    """Versioned metric plugin contract."""

    @property
    def definition(self) -> MetricDefinition:
        """Describe compatibility, output, cost, and aggregation."""

        raise TypeError("protocol declaration has no runtime implementation")

    def evaluate(
        self,
        context: MetricContext,
        configuration: dict[str, Any] | None = None,
    ) -> MetricResult:
        """Evaluate one sample without mutating shared state."""

        raise TypeError("protocol declaration has no runtime implementation")


class MetricExecutionError(RuntimeError):
    """Isolated metric failure retaining stable metric identity."""

    def __init__(self, metric_id: str, message: str) -> None:
        super().__init__(message)
        self.metric_id = metric_id


class MetricRegistry:
    """Explicit registry that rejects conflicting plugin identities."""

    def __init__(self) -> None:
        self._metrics: dict[str, Metric] = {}

    def register(self, metric: Metric) -> None:
        """Register one exact identifier once."""

        identifier = metric.definition.identifier
        if identifier in self._metrics:
            raise ValueError(f"metric identifier is already registered: {identifier}")
        self._metrics[identifier] = metric

    def definitions(self) -> tuple[MetricDefinition, ...]:
        """Return stable sorted metric definitions."""

        return tuple(self._metrics[identifier].definition for identifier in sorted(self._metrics))

    def definition(self, identifier: str) -> MetricDefinition:
        """Return one definition or fail with the stable execution error."""

        try:
            return self._metrics[identifier].definition
        except KeyError as error:
            raise MetricExecutionError(identifier, "metric is not registered") from error

    def evaluate(
        self,
        identifier: str,
        context: MetricContext,
        configuration: dict[str, Any] | None = None,
    ) -> MetricResult:
        """Validate compatibility/config/result and isolate plugin exceptions."""

        try:
            metric = self._metrics[identifier]
        except KeyError as error:
            raise MetricExecutionError(identifier, "metric is not registered") from error
        definition = metric.definition
        if context.task_type not in definition.task_types:
            raise MetricExecutionError(identifier, "metric does not support this task type")
        values = {
            "input": context.input,
            "prediction": context.prediction,
            "reference": context.reference,
            "retrieved_items": context.retrieved_items,
            "trajectory": context.trajectory,
            "operational": context.operational,
        }
        missing = [field for field in definition.required_fields if values.get(field) is None]
        if definition.reference_required and context.reference is None:
            missing.append("reference")
        if missing:
            raise MetricExecutionError(
                identifier,
                f"metric inputs are missing: {', '.join(sorted(set(missing)))}",
            )
        config = configuration or {}
        config_errors = list(
            Draft202012Validator(definition.configuration_schema).iter_errors(config)
        )
        if config_errors:
            raise MetricExecutionError(identifier, config_errors[0].message)
        try:
            result = metric.evaluate(context, config)
        except MetricExecutionError:
            raise
        except Exception as error:
            raise MetricExecutionError(identifier, str(error)) from error
        serialized = {
            "scalar": result.scalar,
            "label": result.label,
            "structured": result.structured,
            "explanation": result.explanation,
            "metadata": result.metadata,
            "missing": result.missing,
        }
        result_errors = list(Draft202012Validator(definition.output_schema).iter_errors(serialized))
        if result_errors:
            raise MetricExecutionError(identifier, "metric returned an invalid result schema")
        if result.scalar is not None:
            if definition.minimum is not None and result.scalar < definition.minimum:
                raise MetricExecutionError(identifier, "metric returned a score below its range")
            if definition.maximum is not None and result.scalar > definition.maximum:
                raise MetricExecutionError(identifier, "metric returned a score above its range")
        return result


RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "scalar": {"type": ["number", "null"]},
        "label": {"type": ["string", "null"]},
        "structured": {"type": ["object", "null"]},
        "explanation": {"type": ["string", "null"]},
        "metadata": {"type": "object"},
        "missing": {"type": "boolean"},
    },
    "required": [
        "scalar",
        "label",
        "structured",
        "explanation",
        "metadata",
        "missing",
    ],
}

EMPTY_CONFIG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "maxProperties": 0,
}
