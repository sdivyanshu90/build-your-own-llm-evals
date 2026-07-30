"""Create immutable dataset registry tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_datasets"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create dataset catalogs, versions, records, and import jobs."""

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.String(100)), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_datasets_project",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "slug",
            name="uq_datasets_project_slug",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_datasets_project_id",
        ),
    )
    op.create_index(
        "ix_datasets_project_created",
        "datasets",
        ["project_id", sa.text("created_at DESC"), "id"],
    )
    op.create_table(
        "dataset_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("schema_name", sa.String(100), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("schema_json", postgresql.JSONB, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False),
        sa.Column("canonicalization_version", sa.String(50), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("record_count", sa.BigInteger, nullable=False),
        sa.Column("duplicate_payload_count", sa.BigInteger, nullable=False),
        sa.Column("split_counts", postgresql.JSONB, nullable=False),
        sa.Column(
            "parent_version_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_id"],
            ["datasets.organization_id", "datasets.project_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_dataset_versions_dataset",
        ),
        sa.UniqueConstraint(
            "dataset_id",
            "version_number",
            name="uq_dataset_versions_number",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_dataset_versions_project_id",
        ),
        sa.CheckConstraint("record_count > 0", name="ck_dataset_versions_records"),
        sa.CheckConstraint(
            "duplicate_payload_count >= 0",
            name="ck_dataset_versions_duplicates",
        ),
        sa.CheckConstraint(
            "state IN ('published', 'deprecated', 'retired')",
            name="ck_dataset_versions_state",
        ),
    )
    op.create_index(
        "ix_dataset_versions_dataset_number",
        "dataset_versions",
        ["dataset_id", "version_number"],
    )
    op.create_table(
        "dataset_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("record_key", sa.String(500), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False),
        sa.Column("splits", postgresql.ARRAY(sa.String(100)), nullable=False),
        sa.Column("source", postgresql.JSONB, nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("envelope_hash", sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_version_id"],
            [
                "dataset_versions.organization_id",
                "dataset_versions.project_id",
                "dataset_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_dataset_records_version",
        ),
        sa.UniqueConstraint(
            "dataset_version_id",
            "record_key",
            name="uq_dataset_records_version_key",
        ),
    )
    op.create_index(
        "ix_dataset_records_payload_hash",
        "dataset_records",
        ["dataset_version_id", "payload_hash"],
    )
    op.create_table(
        "dataset_import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("dataset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column(
            "source_artifact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("artifacts.id", ondelete="RESTRICT"),
        ),
        sa.Column("import_format", sa.String(32), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("records_processed", sa.BigInteger, nullable=False),
        sa.Column("error_count", sa.Integer, nullable=False),
        sa.Column("errors", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_id"],
            ["datasets.organization_id", "datasets.project_id", "datasets.id"],
            ondelete="RESTRICT",
            name="fk_dataset_import_jobs_dataset",
        ),
        sa.UniqueConstraint(
            "project_id",
            "idempotency_key",
            name="uq_dataset_import_jobs_idempotency",
        ),
        sa.CheckConstraint(
            "records_processed >= 0 AND error_count >= 0",
            name="ck_dataset_import_jobs_counts",
        ),
    )
    op.execute(
        """
        CREATE FUNCTION prevent_published_dataset_content_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF OLD.state IN ('published', 'deprecated', 'retired') AND (
            NEW.dataset_id IS DISTINCT FROM OLD.dataset_id OR
            NEW.version_number IS DISTINCT FROM OLD.version_number OR
            NEW.schema_json IS DISTINCT FROM OLD.schema_json OR
            NEW.metadata_json IS DISTINCT FROM OLD.metadata_json OR
            NEW.canonicalization_version IS DISTINCT FROM OLD.canonicalization_version OR
            NEW.content_hash IS DISTINCT FROM OLD.content_hash OR
            NEW.record_count IS DISTINCT FROM OLD.record_count OR
            NEW.parent_version_ids IS DISTINCT FROM OLD.parent_version_ids
          ) THEN
            RAISE EXCEPTION 'published dataset version content is immutable';
          END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER dataset_versions_immutable
        BEFORE UPDATE ON dataset_versions
        FOR EACH ROW EXECUTE FUNCTION prevent_published_dataset_content_change()
        """
    )
    op.execute(
        """
        CREATE FUNCTION prevent_published_dataset_record_change()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM dataset_versions
            WHERE id = OLD.dataset_version_id
              AND state IN ('published', 'deprecated', 'retired')
          ) THEN
            RAISE EXCEPTION 'published dataset records are immutable';
          END IF;
          RETURN COALESCE(NEW, OLD);
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER dataset_records_immutable
        BEFORE UPDATE OR DELETE ON dataset_records
        FOR EACH ROW EXECUTE FUNCTION prevent_published_dataset_record_change()
        """
    )
    for table in ("datasets", "dataset_versions", "dataset_records", "dataset_import_jobs"):
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
    """Remove dataset registry structures."""

    op.execute("DROP TRIGGER dataset_records_immutable ON dataset_records")
    op.execute("DROP FUNCTION prevent_published_dataset_record_change")
    op.execute("DROP TRIGGER dataset_versions_immutable ON dataset_versions")
    op.execute("DROP FUNCTION prevent_published_dataset_content_change")
    op.drop_table("dataset_import_jobs")
    op.drop_table("dataset_records")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
