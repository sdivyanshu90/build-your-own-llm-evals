"""SQLAlchemy experiment, run, task, response, and result models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from eval_platform_domain.ids import new_uuid7
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from eval_platform_infrastructure.database import Base, utc_now
from eval_platform_infrastructure.models import UUID_PK


class SystemSnapshotModel(Base):
    """Immutable secret-free system-under-test snapshot."""

    __tablename__ = "system_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    provider: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ExperimentModel(Base):
    """Immutable resolved experiment."""

    __tablename__ = "experiments"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "system_snapshot_id"],
            [
                "system_snapshots.organization_id",
                "system_snapshots.project_id",
                "system_snapshots.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_version_id"],
            [
                "dataset_versions.organization_id",
                "dataset_versions.project_id",
                "dataset_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        Index("ix_experiments_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    system_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    suite: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seed: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    application_version: Mapped[str] = mapped_column(String(100), nullable=False)
    dependency_lock_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EvaluationRunModel(Base):
    """Durable evaluation run aggregate."""

    __tablename__ = "evaluation_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "experiment_id"],
            ["experiments.organization_id", "experiments.project_id", "experiments.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_runs_project_state_created", "project_id", "state", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    experiment_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    total_tasks: Mapped[int] = mapped_column(BigInteger, nullable=False)
    succeeded_tasks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failed_tasks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cancelled_tasks: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    budget_limit: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    budget_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    actual_cost: Mapped[Decimal] = mapped_column(
        Numeric(30, 12), nullable=False, default=Decimal("0")
    )
    version_stamp: Mapped[int] = mapped_column(Integer, nullable=False)
    fail_fast: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunStateEventModel(Base):
    """Append-only run state transition event."""

    __tablename__ = "run_state_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(40))
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class EvaluationTaskModel(Base):
    """Idempotent natural-key task with renewable lease."""

    __tablename__ = "evaluation_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "record_key", "repetition", "system_snapshot_id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
        ),
        Index("ix_tasks_run_state_key", "run_id", "state", "record_key"),
        Index("ix_tasks_lease_expiry", "state", "lease_expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    repetition: Mapped[int] = mapped_column(Integer, nullable=False)
    system_snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    seed: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(200))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskAttemptModel(Base):
    """Append-only provider attempt."""

    __tablename__ = "task_attempts"
    __table_args__ = (
        UniqueConstraint("task_id", "attempt_number"),
        Index("ix_task_attempts_task", "task_id", "attempt_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_request_id: Mapped[str | None] = mapped_column(String(300))
    error_kind: Mapped[str | None] = mapped_column(String(100))
    retryable: Mapped[bool | None] = mapped_column(Boolean)
    ambiguous_billing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EvaluationSampleModel(Base):
    """One settled record/repetition result."""

    __tablename__ = "evaluation_samples"
    __table_args__ = (
        UniqueConstraint("task_id"),
        Index("ix_samples_run_record", "run_id", "record_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"), nullable=False
    )
    record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ModelResponseModel(Base):
    """Normalized model response and usage."""

    __tablename__ = "model_responses"
    __table_args__ = (UniqueConstraint("sample_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_samples.id", ondelete="RESTRICT"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    finish_reason: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_request_id: Mapped[str | None] = mapped_column(String(300))
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RetrievalTraceModel(Base):
    """RAG retrieval summary with large trace artifact reference."""

    __tablename__ = "retrieval_traces"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_samples.id", ondelete="RESTRICT"), nullable=False
    )
    documents: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    retrieval_latency_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("artifacts.id", ondelete="RESTRICT")
    )


class AgentTrajectoryModel(Base):
    """Agent trajectory summary with optional full artifact."""

    __tablename__ = "agent_trajectories"

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_samples.id", ondelete="RESTRICT"), nullable=False
    )
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    step_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("artifacts.id", ondelete="RESTRICT")
    )


class CostRecordModel(Base):
    """Decimal cost ledger entry."""

    __tablename__ = "cost_records"
    __table_args__ = (Index("ix_cost_records_run", "run_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("evaluation_tasks.id", ondelete="RESTRICT")
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(30, 12), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    estimated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class FailureRecordModel(Base):
    """Sanitized durable failure evidence."""

    __tablename__ = "failure_records"
    __table_args__ = (Index("ix_failure_records_run_category", "run_id", "category"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("evaluation_tasks.id", ondelete="RESTRICT")
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    error_kind: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    retryable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ambiguous_billing: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class MetricResultModel(Base):
    """Isolated per-sample metric success, missing result, or failure."""

    __tablename__ = "metric_results"
    __table_args__ = (
        UniqueConstraint("sample_id", "metric_identifier", "metric_version"),
        Index("ix_metric_results_run_metric", "run_id", "metric_identifier", "sample_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    sample_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_samples.id", ondelete="RESTRICT"), nullable=False
    )
    metric_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scalar: Mapped[float | None] = mapped_column()
    label: Mapped[str | None] = mapped_column(String(200))
    structured: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    explanation: Mapped[str | None] = mapped_column(String(2000))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AggregateResultModel(Base):
    """Incrementally recomputable aggregate with explicit denominators."""

    __tablename__ = "aggregate_results"
    __table_args__ = (
        UniqueConstraint("run_id", "metric_identifier", "metric_version", "slice_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK, ForeignKey("evaluation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    metric_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    metric_version: Mapped[str] = mapped_column(String(50), nullable=False)
    slice_key: Mapped[str] = mapped_column(String(500), nullable=False, default="all")
    value: Mapped[float | None] = mapped_column()
    total_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    available_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    missing_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    failed_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    pending_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
