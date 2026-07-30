"""Create isolated metric and aggregate result tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_metrics"
down_revision: str | None = "0003_evaluation_engine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Create per-sample metric results and denominator-aware aggregates."""

    op.create_table(
        "metric_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "sample_id",
            UUID,
            sa.ForeignKey("evaluation_samples.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric_identifier", sa.String(200), nullable=False),
        sa.Column("metric_version", sa.String(50), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("scalar", sa.Float),
        sa.Column("label", sa.String(200)),
        sa.Column("structured", postgresql.JSONB),
        sa.Column("explanation", sa.String(2000)),
        sa.Column("metadata_json", postgresql.JSONB, nullable=False),
        sa.Column("error", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "sample_id",
            "metric_identifier",
            "metric_version",
            name="uq_metric_results_sample_metric_version",
        ),
        sa.CheckConstraint(
            "status IN ('succeeded','missing','failed')",
            name="ck_metric_results_status",
        ),
    )
    op.create_index(
        "ix_metric_results_run_metric",
        "metric_results",
        ["run_id", "metric_identifier", "sample_id"],
    )
    op.create_table(
        "aggregate_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("metric_identifier", sa.String(200), nullable=False),
        sa.Column("metric_version", sa.String(50), nullable=False),
        sa.Column("slice_key", sa.String(500), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("total_count", sa.BigInteger, nullable=False),
        sa.Column("available_count", sa.BigInteger, nullable=False),
        sa.Column("missing_count", sa.BigInteger, nullable=False),
        sa.Column("failed_count", sa.BigInteger, nullable=False),
        sa.Column("pending_count", sa.BigInteger, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "run_id",
            "metric_identifier",
            "metric_version",
            "slice_key",
            name="uq_aggregate_results_run_metric_slice",
        ),
        sa.CheckConstraint(
            """
            total_count >= 0 AND available_count >= 0 AND missing_count >= 0
            AND failed_count >= 0 AND pending_count >= 0
            AND available_count + missing_count + failed_count + pending_count = total_count
            """,
            name="ck_aggregate_results_counts",
        ),
    )
    op.execute("ALTER TABLE metric_results ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY metric_results_tenant_isolation ON metric_results
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
    """Remove metric storage."""

    op.drop_table("aggregate_results")
    op.drop_table("metric_results")
