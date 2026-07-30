"""Create tenant, credential, audit, idempotency, outbox, and artifact tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create Phase 2 relational structures and tenant RLS policies."""

    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("budget_amount", sa.Numeric(30, 12), nullable=False),
        sa.Column("budget_currency", sa.String(3), nullable=False),
        sa.Column("concurrency_limit", sa.Integer, nullable=False),
        sa.Column("version_stamp", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
        sa.UniqueConstraint("organization_id", "id", name="uq_projects_org_id"),
        sa.CheckConstraint("budget_amount >= 0", name="ck_projects_budget_nonnegative"),
        sa.CheckConstraint(
            "concurrency_limit BETWEEN 1 AND 10000",
            name="ck_projects_concurrency_range",
        ),
    )
    op.create_index(
        "ix_projects_org_created",
        "projects",
        ["organization_id", sa.text("created_at DESC"), "id"],
    )
    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("secret_digest", sa.LargeBinary(32), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("scopes", postgresql.JSONB, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_api_keys_project",
        ),
        sa.UniqueConstraint("prefix", name="uq_api_keys_prefix"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True)),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("actor_subject", sa.String(200), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True)),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("summary", postgresql.JSONB, nullable=False),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "sequence",
            name="uq_audit_events_org_sequence",
        ),
    )
    op.create_index(
        "ix_audit_project_created",
        "audit_events",
        ["project_id", sa.text("created_at DESC"), "id"],
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("principal_subject", sa.String(200), nullable=False),
        sa.Column("route", sa.String(200), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=False),
        sa.Column("response_body", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "principal_subject",
            "route",
            "key",
            name="uq_idempotency_principal_route_key",
        ),
    )
    op.create_index("ix_idempotency_expiry", "idempotency_keys", ["expires_at"])
    op.create_table(
        "outbox_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(150), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("last_error", sa.Text),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox_events",
        ["published_at", "created_at"],
    )
    op.create_table(
        "artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_key", sa.String(1000), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("byte_size", sa.BigInteger, nullable=False),
        sa.Column("media_type", sa.String(200), nullable=False),
        sa.Column("sensitivity", sa.String(32), nullable=False),
        sa.Column("ready", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_artifacts_project",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "object_key",
            name="uq_artifacts_object_key",
        ),
        sa.CheckConstraint("byte_size >= 0", name="ck_artifacts_size_nonnegative"),
    )
    for table in ("projects", "api_keys", "audit_events", "artifacts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (
              organization_id = NULLIF(
                current_setting('app.organization_id', true), ''
              )::uuid
            )
            WITH CHECK (
              organization_id = NULLIF(
                current_setting('app.organization_id', true), ''
              )::uuid
            )
            """
        )


def downgrade() -> None:
    """Remove Phase 2 structures in dependency order."""

    op.drop_table("artifacts")
    op.drop_table("outbox_events")
    op.drop_table("idempotency_keys")
    op.drop_table("audit_events")
    op.drop_table("api_keys")
    op.drop_table("projects")
    op.drop_table("organizations")
