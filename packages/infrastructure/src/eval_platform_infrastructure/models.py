"""Relational models shared by the foundation and later feature phases."""

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
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from eval_platform_infrastructure.database import Base, utc_now

UUID_PK = UUID(as_uuid=True)
MONEY = Numeric(30, 12)


class OrganizationModel(Base):
    """Top-level tenant."""

    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectModel(Base):
    """Organization-owned project and operational policy."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug"),
        UniqueConstraint("organization_id", "id"),
        Index("ix_projects_org_created", "organization_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID_PK,
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("100"))
    budget_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    version_stamp: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ApiKeyModel(Base):
    """Hashed service API key descriptor."""

    __tablename__ = "api_keys"
    __table_args__ = (
        UniqueConstraint("prefix"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    secret_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditEventModel(Base):
    """Append-only, secret-free audit event."""

    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "sequence"),
        Index("ix_audit_project_created", "project_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    actor_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID_PK)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    previous_hash: Mapped[str | None] = mapped_column(String(64))
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class IdempotencyKeyModel(Base):
    """Persisted response for a scoped idempotent operation."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("principal_subject", "route", "key"),
        Index("ix_idempotency_expiry", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    principal_subject: Mapped[str] = mapped_column(String(200), nullable=False)
    route: Mapped[str] = mapped_column(String(200), nullable=False)
    key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OutboxEventModel(Base):
    """Transactional event awaiting broker publication."""

    __tablename__ = "outbox_events"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    event_type: Mapped[str] = mapped_column(String(150), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class ArtifactModel(Base):
    """Verified object-storage artifact descriptor."""

    __tablename__ = "artifacts"
    __table_args__ = (
        UniqueConstraint("organization_id", "project_id", "object_key"),
        ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID_PK, primary_key=True, default=new_uuid7)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID_PK, nullable=False)
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_type: Mapped[str] = mapped_column(String(200), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
