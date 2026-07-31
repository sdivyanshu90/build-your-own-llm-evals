"""Create pairwise, judge, comparison, slice, and gate persistence."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_analysis"
down_revision: str | None = "0004_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Create immutable analysis resources and append-only judgments."""

    op.create_table(
        "rubric_versions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("identifier", sa.String(128), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("instructions", sa.Text, nullable=False),
        sa.Column("dimensions", postgresql.JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_rubric_versions_project",
        ),
        sa.UniqueConstraint(
            "project_id",
            "identifier",
            "version",
            name="uq_rubric_versions_identifier_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_rubric_versions_tenant_id",
        ),
    )
    op.create_table(
        "judge_configurations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("rubric_id", UUID, nullable=False),
        sa.Column("identifier", sa.String(128), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("configuration", postgresql.JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_judge_configurations_project",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "rubric_id"],
            [
                "rubric_versions.organization_id",
                "rubric_versions.project_id",
                "rubric_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_judge_configurations_rubric",
        ),
        sa.UniqueConstraint(
            "project_id",
            "identifier",
            "version",
            name="uq_judge_configurations_identifier_version",
        ),
    )
    op.create_table(
        "pair_designs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("variant_ids", postgresql.JSONB, nullable=False),
        sa.Column("seed", sa.Numeric(20, 0), nullable=False),
        sa.Column("judge_slots", sa.Integer, nullable=False),
        sa.Column("repetitions", sa.Integer, nullable=False),
        sa.Column("reversed_duplicates", sa.Boolean, nullable=False),
        sa.Column("assignment_count", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_pair_designs_project",
        ),
        sa.UniqueConstraint(
            "organization_id", "project_id", "id", name="uq_pair_designs_tenant_id"
        ),
        sa.CheckConstraint(
            "judge_slots > 0 AND repetitions > 0 AND assignment_count > 0",
            name="ck_pair_designs_positive_counts",
        ),
    )
    op.create_index(
        "ix_pair_designs_project_created",
        "pair_designs",
        ["project_id", "created_at", "id"],
    )
    op.create_table(
        "pair_assignments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("design_id", UUID, nullable=False),
        sa.Column("record_key", sa.String(500), nullable=False),
        sa.Column("variant_a_id", sa.String(300), nullable=False),
        sa.Column("variant_b_id", sa.String(300), nullable=False),
        sa.Column("judge_slot", sa.Integer, nullable=False),
        sa.Column("repetition", sa.Integer, nullable=False),
        sa.Column("orientation", sa.Integer, nullable=False),
        sa.Column("order_seed", sa.Numeric(20, 0), nullable=False),
        sa.Column("reverse_of", UUID),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "design_id"],
            ["pair_designs.organization_id", "pair_designs.project_id", "pair_designs.id"],
            ondelete="RESTRICT",
            name="fk_pair_assignments_design",
        ),
        sa.ForeignKeyConstraint(
            ["reverse_of"],
            ["pair_assignments.id"],
            ondelete="RESTRICT",
            name="fk_pair_assignments_reverse",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_pair_assignments_tenant_id",
        ),
        sa.UniqueConstraint(
            "design_id",
            "record_key",
            "variant_a_id",
            "variant_b_id",
            "judge_slot",
            "repetition",
            "orientation",
            name="uq_pair_assignments_cell",
        ),
        sa.CheckConstraint("orientation IN (0, 1)", name="ck_pair_assignments_orientation"),
    )
    op.create_index(
        "ix_pair_assignments_design_record",
        "pair_assignments",
        ["design_id", "record_key", "id"],
    )
    op.create_table(
        "judge_results",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("assignment_id", UUID, nullable=False),
        sa.Column("judge_kind", sa.String(20), nullable=False),
        sa.Column("judge_identifier", sa.String(200), nullable=False),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("scores", postgresql.JSONB, nullable=False),
        sa.Column("evidence", postgresql.JSONB, nullable=False),
        sa.Column("justification", sa.String(2000), nullable=False),
        sa.Column("abstention_reason", sa.String(1000)),
        sa.Column("provider_request_id", sa.String(300)),
        sa.Column("prompt_hash", sa.String(64)),
        sa.Column("usage", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "assignment_id"],
            [
                "pair_assignments.organization_id",
                "pair_assignments.project_id",
                "pair_assignments.id",
            ],
            ondelete="RESTRICT",
            name="fk_judge_results_assignment",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "judge_identifier",
            name="uq_judge_results_assignment_judge",
        ),
        sa.CheckConstraint(
            "judge_kind IN ('human','llm')",
            name="ck_judge_results_kind",
        ),
        sa.CheckConstraint(
            "verdict IN ('A','B','tie','abstain')",
            name="ck_judge_results_verdict",
        ),
        sa.CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_judge_results_confidence",
        ),
    )
    op.create_index(
        "ix_judge_results_assignment",
        "judge_results",
        ["assignment_id", "created_at"],
    )
    op.create_table(
        "comparisons",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("baseline_run_id", UUID, nullable=False),
        sa.Column("candidate_run_id", UUID, nullable=False),
        sa.Column("baseline_dataset_version_id", UUID, nullable=False),
        sa.Column("candidate_dataset_version_id", UUID, nullable=False),
        sa.Column("configuration", postgresql.JSONB, nullable=False),
        sa.Column("results", postgresql.JSONB, nullable=False),
        sa.Column("limitations", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_comparisons_project",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "baseline_run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
            name="fk_comparisons_baseline_run",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "candidate_run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
            name="fk_comparisons_candidate_run",
        ),
    )
    op.create_index(
        "ix_comparisons_project_created",
        "comparisons",
        ["project_id", "created_at", "id"],
    )
    op.create_table(
        "slice_definitions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("identifier", sa.String(128), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("description", sa.String(2000), nullable=False),
        sa.Column("predicate", postgresql.JSONB, nullable=False),
        sa.Column("parent_slice_id", UUID),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_slice_definitions_project",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "parent_slice_id"],
            [
                "slice_definitions.organization_id",
                "slice_definitions.project_id",
                "slice_definitions.id",
            ],
            ondelete="RESTRICT",
            name="fk_slice_definitions_parent",
        ),
        sa.UniqueConstraint(
            "project_id",
            "identifier",
            "version",
            name="uq_slice_definitions_identifier_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_slice_definitions_tenant_id",
        ),
    )
    op.create_table(
        "gate_configurations",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("identifier", sa.String(128), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("configuration", postgresql.JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_gate_configurations_project",
        ),
        sa.UniqueConstraint(
            "project_id",
            "identifier",
            "version",
            name="uq_gate_configurations_identifier_version",
        ),
    )
    tenant_tables = (
        "rubric_versions",
        "judge_configurations",
        "pair_designs",
        "pair_assignments",
        "judge_results",
        "comparisons",
        "slice_definitions",
        "gate_configurations",
    )
    for table in tenant_tables:
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
    """Remove analysis structures in reverse dependency order."""

    op.drop_table("gate_configurations")
    op.drop_table("slice_definitions")
    op.drop_table("comparisons")
    op.drop_table("judge_results")
    op.drop_table("pair_assignments")
    op.drop_table("pair_designs")
    op.drop_table("judge_configurations")
    op.drop_table("rubric_versions")
