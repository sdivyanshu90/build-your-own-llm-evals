"""PostgreSQL experiment and run orchestration repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from eval_platform_application.experiments import (
    Experiment,
    ExperimentRepository,
    MetricOutcome,
    RunCreation,
    SystemSnapshot,
)
from eval_platform_domain.datasets import DatasetVersion
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.execution import (
    ALLOWED_RUN_TRANSITIONS,
    EvaluationRun,
    FailureCategory,
    RunState,
    TaskState,
)
from eval_platform_domain.ids import new_uuid7
from eval_platform_providers.base import GenerationResponse, ProviderError
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eval_platform_infrastructure.dataset_repository import SqlDatasetRepository
from eval_platform_infrastructure.models import OutboxEventModel
from eval_platform_infrastructure.run_models import (
    CostRecordModel,
    EvaluationRunModel,
    EvaluationSampleModel,
    EvaluationTaskModel,
    ExperimentModel,
    FailureRecordModel,
    MetricResultModel,
    ModelResponseModel,
    RunStateEventModel,
    SystemSnapshotModel,
    TaskAttemptModel,
)


class SqlExperimentRepository(ExperimentRepository):
    """Persist immutable experiments and idempotent run tasks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._datasets = SqlDatasetRepository(session)

    async def get_dataset_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        return await self._datasets.get_version(organization_id, project_id, version_id)

    async def add_experiment(self, experiment: Experiment) -> None:
        snapshot = experiment.system_snapshot
        snapshot_model = SystemSnapshotModel(
            id=snapshot.id,
            organization_id=experiment.organization_id,
            project_id=experiment.project_id,
            provider=snapshot.provider,
            model=snapshot.model,
            prompt_template=snapshot.prompt_template,
            parameters=snapshot.parameters,
            content_hash=snapshot.content_hash,
        )
        self._session.add(snapshot_model)
        await self._session.flush((snapshot_model,))
        experiment_model = ExperimentModel(
            id=experiment.id,
            organization_id=experiment.organization_id,
            project_id=experiment.project_id,
            dataset_version_id=experiment.dataset_version_id,
            system_snapshot_id=snapshot.id,
            suite=experiment.suite,
            seed=Decimal(experiment.seed),
            config_hash=experiment.config_hash,
            application_version=experiment.application_version,
            dependency_lock_hash=experiment.dependency_lock_hash,
        )
        self._session.add(experiment_model)
        await self._session.flush((experiment_model,))

    async def get_experiment(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        experiment_id: uuid.UUID,
    ) -> Experiment | None:
        row = (
            await self._session.execute(
                select(ExperimentModel, SystemSnapshotModel)
                .join(
                    SystemSnapshotModel,
                    ExperimentModel.system_snapshot_id == SystemSnapshotModel.id,
                )
                .where(
                    ExperimentModel.organization_id == organization_id,
                    ExperimentModel.project_id == project_id,
                    ExperimentModel.id == experiment_id,
                )
            )
        ).one_or_none()
        if row is None:
            return None
        model, snapshot_model = row
        snapshot = SystemSnapshot(
            id=snapshot_model.id,
            provider=snapshot_model.provider,
            model=snapshot_model.model,
            prompt_template=snapshot_model.prompt_template,
            parameters=snapshot_model.parameters,
            content_hash=snapshot_model.content_hash,
        )
        return Experiment(
            id=model.id,
            organization_id=model.organization_id,
            project_id=model.project_id,
            dataset_version_id=model.dataset_version_id,
            system_snapshot=snapshot,
            suite=model.suite,
            seed=int(model.seed),
            config_hash=model.config_hash,
            application_version=model.application_version,
            dependency_lock_hash=model.dependency_lock_hash,
        )

    async def add_run(self, creation: RunCreation) -> None:
        experiment = await self._session.scalar(
            select(ExperimentModel).where(ExperimentModel.id == creation.run.experiment_id)
        )
        if experiment is None:
            raise DomainError(ErrorCode.NOT_FOUND, "experiment was not found")
        run = creation.run
        run_model = EvaluationRunModel(
            id=run.id,
            organization_id=experiment.organization_id,
            project_id=experiment.project_id,
            experiment_id=experiment.id,
            state=run.state,
            total_tasks=run.total_tasks,
            succeeded_tasks=0,
            failed_tasks=0,
            cancelled_tasks=0,
            budget_limit=creation.budget_limit.amount,
            budget_currency=creation.budget_limit.currency,
            actual_cost=Decimal("0"),
            version_stamp=run.version_stamp,
        )
        self._session.add(run_model)
        await self._session.flush((run_model,))
        self._session.add_all(
            [
                EvaluationTaskModel(
                    id=task.id,
                    organization_id=experiment.organization_id,
                    project_id=experiment.project_id,
                    run_id=run.id,
                    record_key=task.record_key,
                    repetition=task.repetition,
                    system_snapshot_id=task.system_snapshot_id,
                    input_payload=task.input_payload,
                    seed=Decimal(task.seed),
                    state=TaskState.PENDING,
                )
                for task in creation.tasks
            ]
        )
        states = (RunState.DRAFT, RunState.VALIDATING, RunState.QUEUED)
        self._session.add_all(
            [
                RunStateEventModel(
                    organization_id=experiment.organization_id,
                    project_id=experiment.project_id,
                    run_id=run.id,
                    sequence=index,
                    from_state=states[index - 1] if index else None,
                    to_state=state,
                )
                for index, state in enumerate(states)
            ]
        )
        self._session.add(
            OutboxEventModel(
                aggregate_type="evaluation_run",
                aggregate_id=run.id,
                event_type="evaluation.run.queued.v1",
                payload={"run_id": str(run.id)},
            )
        )

    async def get_run(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> EvaluationRun | None:
        model = await self._session.scalar(
            select(EvaluationRunModel).where(
                EvaluationRunModel.organization_id == organization_id,
                EvaluationRunModel.project_id == project_id,
                EvaluationRunModel.id == run_id,
            )
        )
        return None if model is None else _run(model)

    async def get_run_context(
        self,
        run_id: uuid.UUID,
    ) -> tuple[EvaluationRunModel, ExperimentModel, SystemSnapshotModel] | None:
        row = (
            await self._session.execute(
                select(EvaluationRunModel, ExperimentModel, SystemSnapshotModel)
                .join(
                    ExperimentModel,
                    EvaluationRunModel.experiment_id == ExperimentModel.id,
                )
                .join(
                    SystemSnapshotModel,
                    ExperimentModel.system_snapshot_id == SystemSnapshotModel.id,
                )
                .where(EvaluationRunModel.id == run_id)
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1], row[2])

    async def transition_run(
        self,
        run_id: uuid.UUID,
        target: RunState,
        *,
        reason: str | None = None,
    ) -> EvaluationRun:
        model = await self._session.scalar(
            select(EvaluationRunModel).where(EvaluationRunModel.id == run_id).with_for_update()
        )
        if model is None:
            raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
        source = RunState(model.state)
        if target not in ALLOWED_RUN_TRANSITIONS[source]:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"cannot transition run from {source} to {target}",
            )
        sequence = await self._session.scalar(
            select(func.coalesce(func.max(RunStateEventModel.sequence), -1)).where(
                RunStateEventModel.run_id == run_id
            )
        )
        model.state = target
        model.version_stamp += 1
        if target is RunState.RUNNING and model.started_at is None:
            model.started_at = datetime.now(UTC)
        if target in {
            RunState.COMPLETED,
            RunState.COMPLETED_WITH_ERRORS,
            RunState.CANCELLED,
            RunState.FAILED,
        }:
            model.completed_at = datetime.now(UTC)
        self._session.add(
            RunStateEventModel(
                organization_id=model.organization_id,
                project_id=model.project_id,
                run_id=run_id,
                sequence=int(sequence or 0) + 1,
                from_state=source,
                to_state=target,
                reason=reason,
            )
        )
        return _run(model)

    async def claim_next_task(
        self,
        run_id: uuid.UUID,
        *,
        owner: str,
        lease_seconds: int = 120,
    ) -> EvaluationTaskModel | None:
        now = datetime.now(UTC)
        model = await self._session.scalar(
            select(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.run_id == run_id,
                (
                    (EvaluationTaskModel.state == TaskState.PENDING)
                    | (
                        EvaluationTaskModel.state.in_([TaskState.LEASED, TaskState.RUNNING])
                        & (EvaluationTaskModel.lease_expires_at < now)
                    )
                ),
            )
            .order_by(EvaluationTaskModel.record_key, EvaluationTaskModel.repetition)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if model is None:
            return None
        model.state = TaskState.LEASED
        model.lease_owner = owner
        model.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return model

    async def mark_task_running(self, task_id: uuid.UUID, owner: str) -> int:
        model = await self._session.scalar(
            select(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.id == task_id,
                EvaluationTaskModel.state == TaskState.LEASED,
                EvaluationTaskModel.lease_owner == owner,
            )
            .with_for_update()
        )
        if model is None:
            raise DomainError(ErrorCode.CONFLICT, "task lease was lost")
        model.state = TaskState.RUNNING
        model.attempt_count += 1
        self._session.add(
            TaskAttemptModel(
                task_id=task_id,
                attempt_number=model.attempt_count,
                started_at=datetime.now(UTC),
            )
        )
        return model.attempt_count

    async def complete_task_success(
        self,
        task_id: uuid.UUID,
        response: GenerationResponse,
        *,
        latency_ms: int,
        cost: Decimal,
        estimated_cost: bool,
        metric_outcomes: tuple[MetricOutcome, ...] = (),
    ) -> None:
        task = await self._session.scalar(
            select(EvaluationTaskModel).where(EvaluationTaskModel.id == task_id).with_for_update()
        )
        if task is None:
            raise DomainError(ErrorCode.NOT_FOUND, "task was not found")
        if task.state == TaskState.SUCCEEDED:
            return
        if task.state != TaskState.RUNNING:
            raise DomainError(ErrorCode.CONFLICT, "task is not running")
        existing_sample = await self._session.scalar(
            select(EvaluationSampleModel.id).where(EvaluationSampleModel.task_id == task.id)
        )
        if existing_sample is not None:
            task.state = TaskState.SUCCEEDED
            return
        sample_id = new_uuid7()
        self._session.add(
            EvaluationSampleModel(
                id=sample_id,
                organization_id=task.organization_id,
                project_id=task.project_id,
                run_id=task.run_id,
                task_id=task.id,
                record_key=task.record_key,
                status="succeeded",
                latency_ms=latency_ms,
            )
        )
        self._session.add(
            ModelResponseModel(
                sample_id=sample_id,
                text=response.text,
                model=response.model,
                finish_reason=response.finish_reason,
                provider_request_id=response.provider_request_id,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                raw_metadata=response.raw_metadata,
            )
        )
        self._session.add_all(
            [
                MetricResultModel(
                    organization_id=task.organization_id,
                    project_id=task.project_id,
                    run_id=task.run_id,
                    sample_id=sample_id,
                    metric_identifier=outcome.identifier,
                    metric_version=outcome.version,
                    status=outcome.status,
                    scalar=outcome.scalar,
                    label=outcome.label,
                    structured=outcome.structured,
                    explanation=outcome.explanation,
                    metadata_json=outcome.metadata or {},
                    error=outcome.error,
                )
                for outcome in metric_outcomes
            ]
        )
        self._session.add(
            CostRecordModel(
                run_id=task.run_id,
                task_id=task.id,
                kind="provider",
                amount=cost,
                currency=response.usage.currency,
                estimated=estimated_cost,
                source="provider" if response.usage.actual_cost else "pricing_snapshot",
            )
        )
        task.state = TaskState.SUCCEEDED
        task.completed_at = datetime.now(UTC)
        run = await self._session.scalar(
            select(EvaluationRunModel).where(EvaluationRunModel.id == task.run_id).with_for_update()
        )
        if run is None:
            raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
        run.succeeded_tasks += 1
        run.actual_cost += cost
        await self._finalize_if_settled(run)

    async def complete_task_failure(
        self,
        task_id: uuid.UUID,
        error: ProviderError,
        *,
        category: FailureCategory = FailureCategory.PROVIDER,
    ) -> None:
        task = await self._session.scalar(
            select(EvaluationTaskModel).where(EvaluationTaskModel.id == task_id).with_for_update()
        )
        if task is None:
            raise DomainError(ErrorCode.NOT_FOUND, "task was not found")
        if task.state in {TaskState.FAILED, TaskState.SUCCEEDED, TaskState.CANCELLED}:
            return
        task.state = TaskState.FAILED
        task.completed_at = datetime.now(UTC)
        existing_sample = await self._session.scalar(
            select(EvaluationSampleModel.id).where(EvaluationSampleModel.task_id == task.id)
        )
        if existing_sample is None:
            self._session.add(
                EvaluationSampleModel(
                    organization_id=task.organization_id,
                    project_id=task.project_id,
                    run_id=task.run_id,
                    task_id=task.id,
                    record_key=task.record_key,
                    status="failed",
                )
            )
        self._session.add(
            FailureRecordModel(
                run_id=task.run_id,
                task_id=task.id,
                category=category,
                error_kind=error.kind,
                message=error.message[:1000],
                retryable=error.retryable,
                ambiguous_billing=error.ambiguous_billing,
            )
        )
        run = await self._session.scalar(
            select(EvaluationRunModel).where(EvaluationRunModel.id == task.run_id).with_for_update()
        )
        if run is None:
            raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
        run.failed_tasks += 1
        await self._finalize_if_settled(run)

    async def cancel_run(self, run_id: uuid.UUID) -> EvaluationRun:
        model = await self._session.scalar(
            select(EvaluationRunModel).where(EvaluationRunModel.id == run_id).with_for_update()
        )
        if model is None:
            raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
        state = RunState(model.state)
        if state not in {
            RunState.QUEUED,
            RunState.RUNNING,
            RunState.PAUSING,
            RunState.PAUSED,
        }:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                f"cannot cancel run from {state}",
            )
        await self.transition_run(run_id, RunState.CANCELLING)
        cancelled = await self._session.scalar(
            select(func.count())
            .select_from(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.run_id == run_id,
                EvaluationTaskModel.state.in_([TaskState.PENDING, TaskState.LEASED]),
            )
        )
        await self._session.execute(
            update(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.run_id == run_id,
                EvaluationTaskModel.state.in_([TaskState.PENDING, TaskState.LEASED]),
            )
            .values(state=TaskState.CANCELLED, completed_at=datetime.now(UTC))
        )
        model.cancelled_tasks += int(cancelled or 0)
        active = await self._session.scalar(
            select(func.count())
            .select_from(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.run_id == run_id,
                EvaluationTaskModel.state == TaskState.RUNNING,
            )
        )
        if not active:
            await self.transition_run(run_id, RunState.CANCELLED)
        return _run(model)

    async def _finalize_if_settled(self, run: EvaluationRunModel) -> None:
        if RunState(run.state) is RunState.PAUSING:
            active = await self._session.scalar(
                select(func.count())
                .select_from(EvaluationTaskModel)
                .where(
                    EvaluationTaskModel.run_id == run.id,
                    EvaluationTaskModel.state.in_([TaskState.LEASED, TaskState.RUNNING]),
                )
            )
            if not active:
                await self.transition_run(run.id, RunState.PAUSED)
            return
        settled = run.succeeded_tasks + run.failed_tasks + run.cancelled_tasks
        if settled != run.total_tasks:
            return
        state = RunState(run.state)
        if state is RunState.CANCELLING:
            await self.transition_run(run.id, RunState.CANCELLED)
        elif state is RunState.RUNNING:
            target = RunState.COMPLETED_WITH_ERRORS if run.failed_tasks else RunState.COMPLETED
            await self.transition_run(run.id, target)

    async def pause_run(self, run_id: uuid.UUID) -> EvaluationRun:
        """Stop new dispatch and move to paused when active work is settled."""

        model = await self._session.scalar(
            select(EvaluationRunModel).where(EvaluationRunModel.id == run_id).with_for_update()
        )
        if model is None:
            raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
        if RunState(model.state) is not RunState.RUNNING:
            raise DomainError(
                ErrorCode.INVALID_STATE_TRANSITION,
                "only a running run can be paused",
            )
        await self.transition_run(run_id, RunState.PAUSING)
        active = await self._session.scalar(
            select(func.count())
            .select_from(EvaluationTaskModel)
            .where(
                EvaluationTaskModel.run_id == run_id,
                EvaluationTaskModel.state.in_([TaskState.LEASED, TaskState.RUNNING]),
            )
        )
        if not active:
            await self.transition_run(run_id, RunState.PAUSED)
        return _run(model)

    async def resume_run(self, run_id: uuid.UUID) -> EvaluationRun:
        """Queue a paused run and publish an idempotent outbox event."""

        run = await self.transition_run(run_id, RunState.QUEUED)
        self._session.add(
            OutboxEventModel(
                aggregate_type="evaluation_run",
                aggregate_id=run_id,
                event_type="evaluation.run.queued.v1",
                payload={"run_id": str(run_id)},
            )
        )
        return run


def _run(model: EvaluationRunModel) -> EvaluationRun:
    return EvaluationRun(
        id=model.id,
        experiment_id=model.experiment_id,
        state=RunState(model.state),
        total_tasks=model.total_tasks,
        succeeded_tasks=model.succeeded_tasks,
        failed_tasks=model.failed_tasks,
        cancelled_tasks=model.cancelled_tasks,
        version_stamp=model.version_stamp,
    )
