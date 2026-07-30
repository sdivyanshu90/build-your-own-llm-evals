"""Experiment, run, task, and result API schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from pydantic import Field, field_validator

from eval_platform_schemas.common import StrictModel


class ProviderSnapshotInput(StrictModel):
    """Secret-free provider adapter configuration."""

    type: str = Field(pattern="^(fake|openai_compatible|local|generic_http)$")
    identifier: str = Field(min_length=1, max_length=200)
    base_url: str | None = None
    secret_env: str | None = Field(
        default=None,
        pattern="^[A-Z][A-Z0-9_]{0,99}$",
    )
    responses: dict[str, str] = Field(default_factory=dict)


class MetricConfigInput(StrictModel):
    """One exact metric identifier and validated plugin configuration."""

    id: str = Field(min_length=1, max_length=200)
    configuration: dict[str, Any] = Field(default_factory=dict)


class SuiteInput(StrictModel):
    """Versioned evaluation behavior embedded in the initial experiment snapshot."""

    task_type: str = Field(
        default="generation",
        pattern="^(generation|qa|classification|summarization|extraction|rag|agent|conversation)$",
    )
    input_field: str | None = Field(default=None, max_length=200)
    reference_field: str | None = Field(default=None, max_length=200)
    metrics: list[MetricConfigInput] = Field(default_factory=list, max_length=100)
    continue_on_error: bool = True


class ExperimentCreate(StrictModel):
    """Create an immutable experiment."""

    dataset_version_id: uuid.UUID
    provider: ProviderSnapshotInput
    model: str = Field(min_length=1, max_length=200)
    prompt_template: str = Field(min_length=1, max_length=100_000)
    parameters: dict[str, Any] = Field(default_factory=dict)
    suite: SuiteInput
    seed: int = Field(default=0, ge=0, lt=1 << 64)

    @field_validator("prompt_template")
    @classmethod
    def requires_input_marker(cls, value: str) -> str:
        if "{{ input }}" not in value:
            raise ValueError("prompt template must contain {{ input }}")
        return value


class SystemSnapshotRead(StrictModel):
    """Resolved system snapshot."""

    id: uuid.UUID
    provider: dict[str, Any]
    model: str
    prompt_template: str
    parameters: dict[str, Any]
    content_hash: str


class ExperimentRead(StrictModel):
    """Immutable experiment response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    project_id: uuid.UUID
    dataset_version_id: uuid.UUID
    system_snapshot: SystemSnapshotRead
    suite: dict[str, Any]
    seed: int
    config_hash: str
    application_version: str
    dependency_lock_hash: str


class RunStart(StrictModel):
    """Start or reproduce an experiment."""

    repetitions: int = Field(default=1, ge=1, le=100)
    budget_limit: Decimal = Field(default=Decimal("100"), ge=0)


class RunRead(StrictModel):
    """Run state and explicit denominator counters."""

    id: uuid.UUID
    experiment_id: uuid.UUID
    state: str
    total_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    pending_tasks: int
    version_stamp: int


class SampleRead(StrictModel):
    """Per-record evaluation sample."""

    id: uuid.UUID
    task_id: uuid.UUID
    record_key: str
    status: str
    latency_ms: int | None
    response_text: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    failure_category: str | None
    failure_message: str | None


class AggregateRead(StrictModel):
    """Aggregate value with complete result-state denominators."""

    metric_identifier: str
    metric_version: str
    slice_key: str
    value: float | None
    total_count: int
    available_count: int
    missing_count: int
    failed_count: int
    pending_count: int


class RetrievalTraceRead(StrictModel):
    """Retrieved documents and retrieval latency for one RAG sample."""

    sample_id: uuid.UUID
    documents: list[dict[str, Any]]
    retrieval_latency_ms: int
    artifact_id: uuid.UUID | None


class AgentTrajectoryRead(StrictModel):
    """Trajectory steps for one agent sample."""

    sample_id: uuid.UUID
    steps: list[dict[str, Any]]
    step_count: int
    artifact_id: uuid.UUID | None


class CostSummaryRead(StrictModel):
    """Run cost ledger summary."""

    currency: str
    actual: Decimal
    estimated: Decimal
    record_count: int


class ErrorSummaryRead(StrictModel):
    """Failure category count."""

    category: str
    error_kind: str
    count: int
