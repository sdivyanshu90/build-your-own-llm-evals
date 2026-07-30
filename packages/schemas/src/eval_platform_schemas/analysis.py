"""Pairwise, judge, comparison, reporting, slice, and regression-gate schemas."""

from __future__ import annotations

import re
import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from eval_platform_schemas.common import StrictModel


class RubricDimensionInput(StrictModel):
    """One bounded versioned rubric dimension."""

    identifier: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    description: str = Field(min_length=1, max_length=2000)
    minimum: float = 0
    maximum: float = 1
    weight: float = Field(default=1, gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> RubricDimensionInput:
        if self.minimum >= self.maximum:
            raise ValueError("minimum must be lower than maximum")
        return self


class RubricCreate(StrictModel):
    """Create an immutable rubric version."""

    identifier: str = Field(pattern=r"^[a-z][a-z0-9_/-]{0,127}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    title: str = Field(min_length=1, max_length=200)
    instructions: str = Field(min_length=1, max_length=10_000)
    dimensions: list[RubricDimensionInput] = Field(min_length=1, max_length=32)


class RubricRead(RubricCreate):
    """Persisted rubric version."""

    id: uuid.UUID
    project_id: uuid.UUID
    content_hash: str


class JudgeConfigurationCreate(StrictModel):
    """Create a secret-free immutable judge configuration."""

    identifier: str = Field(pattern=r"^[a-z][a-z0-9_/-]{0,127}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    mode: str = Field(
        pattern="^(pointwise|binary|ordinal|rubric|pairwise|groundedness|trajectory)$"
    )
    prompt_version: str = Field(min_length=1, max_length=50)
    rubric_id: uuid.UUID
    repetitions: int = Field(default=1, ge=1, le=20)
    aggregation: str = Field(default="majority", pattern="^(majority|mean|median)$")
    randomize_position: bool = True
    seed: int | None = Field(default=None, ge=0, lt=1 << 64)
    temperature: float = Field(default=0, ge=0, le=2)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    max_attempts: int = Field(default=2, ge=1, le=5)
    max_repairs: int = Field(default=1, ge=0, le=2)
    cost_limit_usd: float = Field(default=1, ge=0)
    calibration_dataset_version_id: uuid.UUID | None = None
    data_handling_policy: str = Field(min_length=1, max_length=2000)


class JudgeConfigurationRead(JudgeConfigurationCreate):
    """Persisted judge configuration."""

    id: uuid.UUID
    project_id: uuid.UUID
    content_hash: str


class PairDesignCreate(StrictModel):
    """Create deterministic blinded pair assignments."""

    name: str = Field(min_length=1, max_length=200)
    record_keys: list[str] = Field(min_length=1, max_length=100_000)
    variant_ids: list[str] = Field(min_length=2, max_length=50)
    judge_slots: int = Field(default=1, ge=1, le=100)
    repetitions: int = Field(default=1, ge=1, le=20)
    seed: int = Field(ge=0, lt=1 << 64)
    sample_size: int | None = Field(default=None, ge=1)
    reversed_duplicates: bool = False


class PairAssignmentRead(StrictModel):
    """Blinded assignment; real identities require judge-assignment access."""

    id: uuid.UUID
    record_key: str
    candidate_a_id: str
    candidate_b_id: str
    judge_slot: int
    repetition: int
    orientation: int
    reverse_of: uuid.UUID | None


class PairDesignRead(StrictModel):
    """Pair design summary with optional assignments."""

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    seed: int
    assignment_count: int
    reversed_duplicates: bool
    assignments: list[PairAssignmentRead] = Field(default_factory=list)


class JudgmentCreate(StrictModel):
    """Submit one human or LLM judgment against a blinded assignment."""

    judge_kind: Literal["human", "llm"]
    judge_identifier: str = Field(min_length=1, max_length=200)
    verdict: Literal["A", "B", "tie", "abstain"]
    confidence: float = Field(ge=0, le=1)
    scores: dict[str, float] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list, max_length=64)
    justification: str = Field(min_length=1, max_length=2000)
    abstention_reason: str | None = Field(default=None, max_length=1000)
    schema_version: Literal["judge-response/1"] = "judge-response/1"

    @field_validator("evidence")
    @classmethod
    def evidence_uses_bounded_references(cls, value: list[str]) -> list[str]:
        """Accept only line references into explicitly delimited prompt sections."""

        if len(value) != len(set(value)):
            raise ValueError("evidence references must be unique")
        if any(re.fullmatch(r"(?:A|B|R|T):L[0-9]{4}", item) is None for item in value):
            raise ValueError("evidence must use A|B|R|T:Ldddd line references")
        return value

    @model_validator(mode="after")
    def consistent_abstention(self) -> JudgmentCreate:
        if self.verdict == "abstain" and not self.abstention_reason:
            raise ValueError("abstention_reason is required")
        if self.verdict != "abstain" and self.abstention_reason is not None:
            raise ValueError("abstention_reason is only valid for abstentions")
        return self


class JudgmentRead(JudgmentCreate):
    """Stored auditable judgment."""

    id: uuid.UUID
    assignment_id: uuid.UUID


class PairAggregateRead(StrictModel):
    """Pair outcomes and bias diagnostics with explicit denominators."""

    assignment_count: int
    judgment_count: int
    wins_a: int
    wins_b: int
    ties: int
    abstentions: int
    usable_count: int
    tie_adjusted_a_win_rate: float | None
    disagreement_rate: float | None
    position_a_win_rate: float | None


class MissingDataPolicy(StrEnum):
    """Supported comparison policies; exclusion is always visible."""

    AVAILABLE_PAIRS = "available_pairs"
    FAILURES_AS_ZERO = "failures_as_zero"


class ComparisonCreate(StrictModel):
    """Compare two completed or partially completed runs."""

    baseline_run_id: uuid.UUID
    candidate_run_id: uuid.UUID
    metric_identifiers: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=0.95, gt=0, lt=1)
    bootstrap_method: str = Field(default="bca", pattern="^(percentile|basic|bca)$")
    bootstrap_resamples: int = Field(default=10_000, ge=200, le=200_000)
    test: str = Field(
        default="permutation",
        pattern="^(paired_t|wilcoxon|sign|permutation|paired_bootstrap)$",
    )
    seed: int = Field(default=0, ge=0, lt=1 << 64)
    missing_data_policy: MissingDataPolicy = MissingDataPolicy.AVAILABLE_PAIRS
    practical_difference: float = Field(default=0, ge=0)
    allow_dataset_intersection: bool = False
    top_changed_examples: int = Field(default=10, ge=0, le=100)


class IntervalRead(StrictModel):
    """Serialized confidence interval."""

    lower: float
    upper: float
    confidence: float
    method: str


class MetricComparisonRead(StrictModel):
    """Paired comparison for one versioned metric."""

    metric_identifier: str
    metric_version: str
    baseline_mean: float
    candidate_mean: float
    mean_difference: float
    median_difference: float
    relative_improvement: float | None
    probability_of_superiority: float
    standardized_mean_difference: float | None
    confidence_interval: IntervalRead
    p_value: float
    adjusted_p_value: float | None = None
    test_method: str
    total_union_count: int
    paired_count: int
    missing_baseline_count: int
    missing_candidate_count: int
    failed_baseline_count: int
    failed_candidate_count: int
    practical_interpretation: str
    warnings: list[dict[str, str]]
    largest_improvements: list[dict[str, Any]]
    largest_regressions: list[dict[str, Any]]


class ComparisonRead(StrictModel):
    """Reproducible multi-metric experiment comparison."""

    id: uuid.UUID
    project_id: uuid.UUID
    baseline_run_id: uuid.UUID
    candidate_run_id: uuid.UUID
    baseline_dataset_version_id: uuid.UUID
    candidate_dataset_version_id: uuid.UUID
    dataset_compatible: bool
    intersection_only: bool
    configuration: ComparisonCreate
    metrics: list[MetricComparisonRead]
    limitations: list[str]


class SliceCreate(StrictModel):
    """Versioned safe declarative slice definition."""

    identifier: str = Field(pattern=r"^[a-z][a-z0-9_/-]{0,127}$")
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    description: str = Field(min_length=1, max_length=2000)
    predicate: dict[str, Any]
    parent_slice_id: uuid.UUID | None = None


class SliceRead(SliceCreate):
    """Persisted slice definition."""

    id: uuid.UUID
    project_id: uuid.UUID
    content_hash: str


class GateOperator(StrEnum):
    """Supported quality-gate predicates."""

    MINIMUM = "minimum"
    MAXIMUM = "maximum"
    MAXIMUM_REGRESSION = "maximum_regression"
    LOWER_CONFIDENCE_MINIMUM = "lower_confidence_minimum"
    NO_MEANINGFUL_REGRESSION = "no_meaningful_regression"


class GateRule(StrictModel):
    """One machine-readable, version-controlled gate rule."""

    identifier: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    metric_identifier: str = Field(min_length=1, max_length=200)
    operator: GateOperator
    threshold: float
    minimum_paired_count: int = Field(default=1, ge=1)
    required: bool = True


class GateConfiguration(StrictModel):
    """Versioned set of regression criteria."""

    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    rules: list[GateRule] = Field(min_length=1, max_length=200)


class GateRuleResult(StrictModel):
    """One evaluated gate result with evidence."""

    identifier: str
    passed: bool
    required: bool
    observed: float | None
    threshold: float
    message: str


class GateResult(StrictModel):
    """Aggregate gate outcome used as the CLI process result."""

    passed: bool
    rules: list[GateRuleResult]


class AuditEventRead(StrictModel):
    """Secret-free append-only audit event."""

    id: uuid.UUID
    sequence: int
    project_id: uuid.UUID | None
    actor_subject: str
    action: str
    target_type: str
    target_id: uuid.UUID | None
    outcome: str
    request_id: str
    summary: dict[str, Any]
    previous_hash: str | None
    event_hash: str
