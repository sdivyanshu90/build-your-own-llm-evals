"""Create immutable experiments and resumable evaluation execution tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_evaluation_engine"
down_revision: str | None = "0002_datasets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    """Create Phase 4 configuration, execution, usage, and artifact references."""

    op.create_table(
        "system_snapshots",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("provider", postgresql.JSONB, nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("parameters", postgresql.JSONB, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id"],
            ["projects.organization_id", "projects.id"],
            ondelete="RESTRICT",
            name="fk_system_snapshots_project",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_system_snapshots_project_id",
        ),
    )
    op.create_table(
        "experiments",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("dataset_version_id", UUID, nullable=False),
        sa.Column("system_snapshot_id", UUID, nullable=False),
        sa.Column("suite", postgresql.JSONB, nullable=False),
        sa.Column("seed", sa.Numeric(20, 0), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("application_version", sa.String(100), nullable=False),
        sa.Column("dependency_lock_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "system_snapshot_id"],
            [
                "system_snapshots.organization_id",
                "system_snapshots.project_id",
                "system_snapshots.id",
            ],
            ondelete="RESTRICT",
            name="fk_experiments_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "dataset_version_id"],
            [
                "dataset_versions.organization_id",
                "dataset_versions.project_id",
                "dataset_versions.id",
            ],
            ondelete="RESTRICT",
            name="fk_experiments_dataset_version",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_experiments_project_id",
        ),
        sa.CheckConstraint(
            "seed >= 0 AND seed < 18446744073709551616",
            name="ck_experiments_seed",
        ),
    )
    op.create_index(
        "ix_experiments_project_created",
        "experiments",
        ["project_id", sa.text("created_at DESC"), "id"],
    )
    op.create_table(
        "evaluation_runs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("experiment_id", UUID, nullable=False),
        sa.Column("state", sa.String(40), nullable=False),
        sa.Column("total_tasks", sa.BigInteger, nullable=False),
        sa.Column("succeeded_tasks", sa.BigInteger, nullable=False),
        sa.Column("failed_tasks", sa.BigInteger, nullable=False),
        sa.Column("cancelled_tasks", sa.BigInteger, nullable=False),
        sa.Column("budget_limit", sa.Numeric(30, 12), nullable=False),
        sa.Column("budget_currency", sa.String(3), nullable=False),
        sa.Column("actual_cost", sa.Numeric(30, 12), nullable=False),
        sa.Column("version_stamp", sa.Integer, nullable=False),
        sa.Column("fail_fast", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "experiment_id"],
            ["experiments.organization_id", "experiments.project_id", "experiments.id"],
            ondelete="RESTRICT",
            name="fk_evaluation_runs_experiment",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "project_id",
            "id",
            name="uq_evaluation_runs_project_id",
        ),
        sa.CheckConstraint(
            """
            total_tasks >= 0 AND succeeded_tasks >= 0 AND failed_tasks >= 0
            AND cancelled_tasks >= 0
            AND succeeded_tasks + failed_tasks + cancelled_tasks <= total_tasks
            """,
            name="ck_evaluation_runs_counters",
        ),
        sa.CheckConstraint(
            "budget_limit >= 0 AND actual_cost >= 0",
            name="ck_evaluation_runs_cost",
        ),
        sa.CheckConstraint(
            """
            state IN (
              'draft', 'validating', 'queued', 'running', 'pausing', 'paused',
              'cancelling', 'cancelled', 'completed', 'completed_with_errors', 'failed'
            )
            """,
            name="ck_evaluation_runs_state",
        ),
    )
    op.create_index(
        "ix_runs_project_state_created",
        "evaluation_runs",
        ["project_id", "state", sa.text("created_at DESC"), "id"],
    )
    op.create_table(
        "run_state_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("sequence", sa.BigInteger, nullable=False),
        sa.Column("from_state", sa.String(40)),
        sa.Column("to_state", sa.String(40), nullable=False),
        sa.Column("reason", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
            name="fk_run_state_events_run",
        ),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_run_state_events_sequence",
        ),
    )
    op.create_table(
        "evaluation_tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_id", UUID, nullable=False),
        sa.Column("run_id", UUID, nullable=False),
        sa.Column("record_key", sa.String(500), nullable=False),
        sa.Column("repetition", sa.Integer, nullable=False),
        sa.Column("system_snapshot_id", UUID, nullable=False),
        sa.Column("input_payload", postgresql.JSONB, nullable=False),
        sa.Column("seed", sa.Numeric(20, 0), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer, nullable=False),
        sa.Column("lease_owner", sa.String(200)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["organization_id", "project_id", "run_id"],
            [
                "evaluation_runs.organization_id",
                "evaluation_runs.project_id",
                "evaluation_runs.id",
            ],
            ondelete="RESTRICT",
            name="fk_evaluation_tasks_run",
        ),
        sa.UniqueConstraint(
            "run_id",
            "record_key",
            "repetition",
            "system_snapshot_id",
            name="uq_evaluation_tasks_natural_key",
        ),
        sa.CheckConstraint("repetition >= 0", name="ck_evaluation_tasks_repetition"),
        sa.CheckConstraint("attempt_count >= 0", name="ck_evaluation_tasks_attempts"),
        sa.CheckConstraint(
            "seed >= 0 AND seed < 18446744073709551616",
            name="ck_evaluation_tasks_seed",
        ),
        sa.CheckConstraint(
            "state IN ('pending','leased','running','succeeded','failed','cancelled')",
            name="ck_evaluation_tasks_state",
        ),
    )
    op.create_index(
        "ix_tasks_run_state_key",
        "evaluation_tasks",
        ["run_id", "state", "record_key"],
    )
    op.create_index(
        "ix_tasks_lease_expiry",
        "evaluation_tasks",
        ["state", "lease_expires_at"],
    )
    op.create_table(
        "task_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("provider_request_id", sa.String(300)),
        sa.Column("error_kind", sa.String(100)),
        sa.Column("retryable", sa.Boolean),
        sa.Column("ambiguous_billing", sa.Boolean, nullable=False),
        sa.UniqueConstraint(
            "task_id",
            "attempt_number",
            name="uq_task_attempts_number",
        ),
    )
    op.create_index(
        "ix_task_attempts_task",
        "task_attempts",
        ["task_id", "attempt_number"],
    )
    op.create_table(
        "evaluation_samples",
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
            "task_id",
            UUID,
            sa.ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("record_key", sa.String(500), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("latency_ms", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", name="uq_evaluation_samples_task_id"),
        sa.CheckConstraint(
            "status IN ('succeeded','failed','cancelled')",
            name="ck_evaluation_samples_status",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_evaluation_samples_latency",
        ),
    )
    op.create_index(
        "ix_samples_run_record",
        "evaluation_samples",
        ["run_id", "record_key"],
    )
    op.create_table(
        "model_responses",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "sample_id",
            UUID,
            sa.ForeignKey("evaluation_samples.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("finish_reason", sa.String(100), nullable=False),
        sa.Column("provider_request_id", sa.String(300)),
        sa.Column("input_tokens", sa.BigInteger, nullable=False),
        sa.Column("output_tokens", sa.BigInteger, nullable=False),
        sa.Column("raw_metadata", postgresql.JSONB, nullable=False),
        sa.UniqueConstraint("sample_id", name="uq_model_responses_sample_id"),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0",
            name="ck_model_responses_tokens",
        ),
    )
    op.create_table(
        "retrieval_traces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "sample_id",
            UUID,
            sa.ForeignKey("evaluation_samples.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("documents", postgresql.JSONB, nullable=False),
        sa.Column("retrieval_latency_ms", sa.BigInteger, nullable=False),
        sa.Column("artifact_id", UUID, sa.ForeignKey("artifacts.id", ondelete="RESTRICT")),
        sa.CheckConstraint(
            "retrieval_latency_ms >= 0",
            name="ck_retrieval_traces_latency",
        ),
    )
    op.create_table(
        "agent_trajectories",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "sample_id",
            UUID,
            sa.ForeignKey("evaluation_samples.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("steps", postgresql.JSONB, nullable=False),
        sa.Column("step_count", sa.Integer, nullable=False),
        sa.Column("artifact_id", UUID, sa.ForeignKey("artifacts.id", ondelete="RESTRICT")),
        sa.CheckConstraint("step_count >= 0", name="ck_agent_trajectories_steps"),
    )
    op.create_table(
        "cost_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(30, 12), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("estimated", sa.Boolean, nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount >= 0", name="ck_cost_records_amount"),
    )
    op.create_index(
        "ix_cost_records_run",
        "cost_records",
        ["run_id", "created_at"],
    )
    op.create_table(
        "failure_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "run_id",
            UUID,
            sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "task_id",
            UUID,
            sa.ForeignKey("evaluation_tasks.id", ondelete="RESTRICT"),
        ),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("error_kind", sa.String(100), nullable=False),
        sa.Column("message", sa.String(1000), nullable=False),
        sa.Column("retryable", sa.Boolean, nullable=False),
        sa.Column("ambiguous_billing", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_failure_records_run_category",
        "failure_records",
        ["run_id", "category"],
    )
    for table in (
        "system_snapshots",
        "experiments",
        "evaluation_runs",
        "run_state_events",
        "evaluation_tasks",
        "evaluation_samples",
    ):
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
    op.execute(
        """
        CREATE FUNCTION enforce_run_transition()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.state = OLD.state THEN
            RETURN NEW;
          END IF;
          IF NOT (
            (OLD.state = 'draft' AND NEW.state = 'validating') OR
            (OLD.state = 'validating' AND NEW.state IN ('draft','queued')) OR
            (OLD.state = 'queued' AND NEW.state IN ('running','cancelling','failed')) OR
            (OLD.state = 'running' AND NEW.state IN (
              'pausing','cancelling','completed','completed_with_errors','failed'
            )) OR
            (OLD.state = 'pausing' AND NEW.state IN ('paused','cancelling')) OR
            (OLD.state = 'paused' AND NEW.state IN ('queued','cancelling')) OR
            (OLD.state = 'cancelling' AND NEW.state = 'cancelled')
          ) THEN
            RAISE EXCEPTION 'invalid evaluation run state transition: % -> %',
              OLD.state, NEW.state;
          END IF;
          RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER evaluation_run_transition_guard
        BEFORE UPDATE OF state ON evaluation_runs
        FOR EACH ROW EXECUTE FUNCTION enforce_run_transition()
        """
    )


def downgrade() -> None:
    """Remove execution structures in dependency order."""

    op.execute("DROP TRIGGER evaluation_run_transition_guard ON evaluation_runs")
    op.execute("DROP FUNCTION enforce_run_transition")
    op.drop_table("failure_records")
    op.drop_table("cost_records")
    op.drop_table("agent_trajectories")
    op.drop_table("retrieval_traces")
    op.drop_table("model_responses")
    op.drop_table("evaluation_samples")
    op.drop_table("task_attempts")
    op.drop_table("evaluation_tasks")
    op.drop_table("run_state_events")
    op.drop_table("evaluation_runs")
    op.drop_table("experiments")
    op.drop_table("system_snapshots")
