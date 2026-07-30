"""SQLAlchemy dataset registry models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from eval_platform_domain.ids import new_uuid7
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from eval_platform_infrastructure.database import Base, utc_now
from eval_platform_infrastructure.models import UUID_PK


class DatasetModel(Base):
    """Dataset catalog identity."""

    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "slug"),
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_datasets_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetVersionModel(Base):
    """Immutable published dataset manifest."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_number"),
        UniqueConstraint("organization_id", "project_id", "id"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_id"],
            ["datasets.organization_id", "datasets.project_id", "datasets.id"],
            ondelete="RESTRICT",
        ),
        Index("ix_dataset_versions_dataset_number", "dataset_id", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    canonicalization_version: Mapped[str] = mapped_column(String(50), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    record_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duplicate_payload_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    split_counts: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False)
    parent_version_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID_PK), nullable=False, default=list
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class DatasetRecordModel(Base):
    """Canonical normalized record."""

    __tablename__ = "dataset_records"
    __table_args__ = (
        UniqueConstraint("dataset_version_id", "record_key"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_version_id"],
            [
                "dataset_versions.organization_id",
                "dataset_versions.project_id",
                "dataset_versions.id",
            ],
            ondelete="RESTRICT",
        ),
        Index("ix_dataset_records_payload_hash", "dataset_version_id", "payload_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dataset_version_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    record_key: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    splits: Mapped[list[str]] = mapped_column(ARRAY(String(100)), nullable=False)
    source: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    envelope_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class DatasetImportJobModel(Base):
    """Durable import job status and bounded diagnostics."""

    __tablename__ = "dataset_import_jobs"
    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key"),
        ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_id"],
            ["datasets.organization_id", "datasets.project_id", "datasets.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    source_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_PK, ForeignKey("artifacts.id", ondelete="RESTRICT")
    )
    import_format: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    records_processed: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
