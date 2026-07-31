"""Durable pairwise, judge, slice, comparison, gate, and report models."""

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


class RubricVersionModel(Base):
    """Immutable project-scoped rubric."""

    __tablename__ = "rubric_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "identifier", "version"),
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
    identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    dimensions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class JudgeConfigurationModel(Base):
    """Immutable, secret-free model-judge configuration."""

    __tablename__ = "judge_configurations"
    __table_args__ = (
        UniqueConstraint("project_id", "identifier", "version"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "rubric_id"],
            [
                "rubric_versions.organization_id",
                "rubric_versions.project_id",
                "rubric_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    rubric_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PairDesignModel(Base):
    """Immutable deterministic pair assignment design."""

    __tablename__ = "pair_designs"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_pair_designs_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    seed: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    judge_slots: Mapped[int] = mapped_column(Integer, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False)
    reversed_duplicates: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assignment_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class PairAssignmentModel(Base):
    """Blinded assignment with server-only variant identity mapping."""

    __tablename__ = "pair_assignments"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "id"),
        UniqueConstraint(
            "design_id",
            "record_key",
            "variant_a_id",
            "variant_b_id",
            "judge_slot",
            "repetition",
            "orientation",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "design_id"],
            ["pair_designs.organization_id", "pair_designs.project_id", "pair_designs.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_pair_assignments_design_record", "design_id", "record_key", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    design_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    variant_a_id: Mapped[str] = mapped_column(String(300), nullable=False)
    variant_b_id: Mapped[str] = mapped_column(String(300), nullable=False)
    judge_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    repetition: Mapped[int] = mapped_column(Integer, nullable=False)
    orientation: Mapped[int] = mapped_column(Integer, nullable=False)
    order_seed: Mapped[Decimal] = mapped_column(Numeric(20, 0), nullable=False)
    reverse_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pair_assignments.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class JudgeResultModel(Base):
    """Append-only human or LLM judgment."""

    __tablename__ = "judge_results"
    __table_args__ = (
        UniqueConstraint("assignment_id", "judge_identifier"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "assignment_id"],
            [
                "pair_assignments.organization_id",
                "pair_assignments.project_id",
                "pair_assignments.id",
            ],
            ondelete="RESTRICT",
        ),
        Index("ix_judge_results_assignment", "assignment_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    judge_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    judge_identifier: Mapped[str] = mapped_column(String(200), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    verdict: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    scores: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    justification: Mapped[str] = mapped_column(String(2000), nullable=False)
    abstention_reason: Mapped[str | None] = mapped_column(String(1000))
    provider_request_id: Mapped[str | None] = mapped_column(String(300))
    prompt_hash: Mapped[str | None] = mapped_column(String(64))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class ComparisonModel(Base):
    """Immutable stored experiment comparison and analysis provenance."""

    __tablename__ = "comparisons"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "project_id", "baseline_run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "candidate_run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_comparisons_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    baseline_run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    candidate_run_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    baseline_dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    candidate_dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class SliceDefinitionModel(Base):
    """Immutable declarative slice definition."""

    __tablename__ = "slice_definitions"
    __table_args__ = (
        UniqueConstraint("project_id", "identifier", "version"),
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "parent_slice_id"],
            [
                "slice_definitions.organization_id",
                "slice_definitions.project_id",
                "slice_definitions.id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    predicate: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parent_slice_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class GateConfigurationModel(Base):
    """Versioned project quality gate."""

    __tablename__ = "gate_configurations"
    __table_args__ = (
        UniqueConstraint("project_id", "identifier", "version"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
