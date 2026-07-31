"""Experiment, asynchronous run, and result endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path

from eval_platform_application.experiments import Experiment, ExperimentService
from eval_platform_domain.auth import Action, authorize
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.execution import EvaluationRun
from eval_platform_domain.money import Money
from eval_platform_infrastructure.run_models import (
    AgentTrajectoryModel,
    AggregateResultModel,
    CostRecordModel,
    EvaluationRunModel,
    EvaluationSampleModel,
    FailureRecordModel,
    ModelResponseModel,
    RetrievalTraceModel,
)
from eval_platform_infrastructure.run_repository import SqlExperimentRepository
from eval_platform_schemas.common import Page, PageMetadata
from eval_platform_schemas.experiments import (
    AgentTrajectoryRead,
    AggregateRead,
    CostSummaryRead,
    ErrorSummaryRead,
    ExperimentCreate,
    ExperimentRead,
    RetrievalTraceRead,
    RunRead,
    RunStart,
    SampleRead,
    SystemSnapshotRead,
)
from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from eval_platform_api.dependencies import (
    PrincipalDependency,
    SessionDependency,
    SettingsDependency,
)

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["experiments"])


def _experiment_read(experiment: Experiment) -> ExperimentRead:
    snapshot = experiment.system_snapshot
    return ExperimentRead(
        id=experiment.id,
        organization_id=experiment.organization_id,
        project_id=experiment.project_id,
        dataset_version_id=experiment.dataset_version_id,
        system_snapshot=SystemSnapshotRead(
            id=snapshot.id,
            provider=snapshot.provider,
            model=snapshot.model,
            prompt_template=snapshot.prompt_template,
            parameters=snapshot.parameters,
            content_hash=snapshot.content_hash,
        ),
        suite=experiment.suite,
        seed=experiment.seed,
        config_hash=experiment.config_hash,
        application_version=experiment.application_version,
        dependency_lock_hash=experiment.dependency_lock_hash,
    )


def _run_read(run: EvaluationRun) -> RunRead:
    settled = run.succeeded_tasks + run.failed_tasks + run.cancelled_tasks
    return RunRead(
        id=run.id,
        experiment_id=run.experiment_id,
        state=run.state,
        total_tasks=run.total_tasks,
        succeeded_tasks=run.succeeded_tasks,
        failed_tasks=run.failed_tasks,
        cancelled_tasks=run.cancelled_tasks,
        pending_tasks=run.total_tasks - settled,
        version_stamp=run.version_stamp,
    )


def _lock_hash() -> str:
    path = Path("uv.lock")
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "unavailable"


@router.post(
    "/experiments",
    response_model=ExperimentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_experiment(
    project_id: uuid.UUID,
    body: ExperimentCreate,
    principal: PrincipalDependency,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ExperimentRead:
    """Resolve all references and create an immutable experiment."""

    experiment = await ExperimentService(SqlExperimentRepository(session)).create_experiment(
        principal,
        project_id=project_id,
        dataset_version_id=body.dataset_version_id,
        provider=body.provider.model_dump(mode="json", exclude_none=True),
        model=body.model,
        prompt_template=body.prompt_template,
        parameters=body.parameters,
        suite=body.suite.model_dump(mode="json"),
        seed=body.seed,
        application_version=settings.service_version,
        dependency_lock_hash=_lock_hash(),
    )
    return _experiment_read(experiment)


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
async def get_experiment(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> ExperimentRead:
    """Get a tenant-scoped immutable experiment."""

    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    experiment = await SqlExperimentRepository(session).get_experiment(
        principal.organization_id,
        project_id,
        experiment_id,
    )
    if experiment is None:
        raise DomainError(ErrorCode.NOT_FOUND, "experiment was not found")
    return _experiment_read(experiment)


@router.post(
    "/experiments/{experiment_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    project_id: uuid.UUID,
    experiment_id: uuid.UUID,
    body: RunStart,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RunRead:
    """Create bounded tasks and publish the run through the transactional outbox."""

    repository = SqlExperimentRepository(session)
    experiment = await repository.get_experiment(
        principal.organization_id,
        project_id,
        experiment_id,
    )
    if experiment is None:
        raise DomainError(ErrorCode.NOT_FOUND, "experiment was not found")
    version = await repository.get_dataset_version(
        principal.organization_id,
        project_id,
        experiment.dataset_version_id,
    )
    if version is None:
        raise DomainError(ErrorCode.NOT_FOUND, "dataset version was not found")
    creation = await ExperimentService(repository).create_run(
        principal,
        experiment=experiment,
        dataset_version=version,
        repetitions=body.repetitions,
        budget_limit=Money(body.budget_limit),
    )
    return _run_read(creation.run)


@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RunRead:
    """Get durable run progress."""

    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    run = await SqlExperimentRepository(session).get_run(
        principal.organization_id,
        project_id,
        run_id,
    )
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    return _run_read(run)


@router.get("/runs", response_model=Page[RunRead])
async def list_runs(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    after: uuid.UUID | None = None,
) -> Page[RunRead]:
    """List project runs with keyset pagination."""

    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    statement = (
        select(EvaluationRunModel)
        .where(
            EvaluationRunModel.organization_id == principal.organization_id,
            EvaluationRunModel.project_id == project_id,
        )
        .order_by(EvaluationRunModel.id)
        .limit(limit + 1)
    )
    if after is not None:
        statement = statement.where(EvaluationRunModel.id > after)
    runs = list((await session.scalars(statement)).all())
    has_more = len(runs) > limit
    runs = runs[:limit]
    return Page(
        items=[_run_model_read(run) for run in runs],
        page=PageMetadata(
            next_cursor=str(runs[-1].id) if has_more and runs else None,
            limit=limit,
        ),
    )


def _run_model_read(run: EvaluationRunModel) -> RunRead:
    settled = run.succeeded_tasks + run.failed_tasks + run.cancelled_tasks
    return RunRead(
        id=run.id,
        experiment_id=run.experiment_id,
        state=run.state,
        total_tasks=run.total_tasks,
        succeeded_tasks=run.succeeded_tasks,
        failed_tasks=run.failed_tasks,
        cancelled_tasks=run.cancelled_tasks,
        pending_tasks=run.total_tasks - settled,
        version_stamp=run.version_stamp,
    )


@router.post("/runs/{run_id}/pause", response_model=RunRead)
async def pause_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RunRead:
    """Cooperatively pause a running evaluation."""

    authorize(
        principal,
        Action.RUN_CANCEL,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    existing = await SqlExperimentRepository(session).get_run(
        principal.organization_id, project_id, run_id
    )
    if existing is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    return _run_read(await SqlExperimentRepository(session).pause_run(run_id))


@router.post("/runs/{run_id}/resume", response_model=RunRead)
async def resume_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RunRead:
    """Resume a paused run without recreating successful work."""

    authorize(
        principal,
        Action.RUN_START,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    existing = await SqlExperimentRepository(session).get_run(
        principal.organization_id, project_id, run_id
    )
    if existing is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    return _run_read(await SqlExperimentRepository(session).resume_run(run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunRead)
async def cancel_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RunRead:
    """Cooperatively cancel queued and active work."""

    authorize(
        principal,
        Action.RUN_CANCEL,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    existing = await SqlExperimentRepository(session).get_run(
        principal.organization_id, project_id, run_id
    )
    if existing is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    return _run_read(await SqlExperimentRepository(session).cancel_run(run_id))


@router.get("/runs/{run_id}/results", response_model=Page[SampleRead])
async def list_results(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=200),
    after: uuid.UUID | None = None,
) -> Page[SampleRead]:
    """List per-record results, preserving failures and missing outputs."""

    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    run = await SqlExperimentRepository(session).get_run(
        principal.organization_id, project_id, run_id
    )
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    statement = (
        select(
            EvaluationSampleModel,
            ModelResponseModel,
            FailureRecordModel,
        )
        .outerjoin(
            ModelResponseModel,
            ModelResponseModel.sample_id == EvaluationSampleModel.id,
        )
        .outerjoin(
            FailureRecordModel,
            FailureRecordModel.task_id == EvaluationSampleModel.task_id,
        )
        .where(
            EvaluationSampleModel.organization_id == principal.organization_id,
            EvaluationSampleModel.project_id == project_id,
            EvaluationSampleModel.run_id == run_id,
        )
        .order_by(EvaluationSampleModel.id)
        .limit(limit + 1)
    )
    if after is not None:
        statement = statement.where(EvaluationSampleModel.id > after)
    rows = (await session.execute(statement)).all()
    has_more = len(rows) > limit
    page = rows[:limit]
    items = [
        SampleRead(
            id=sample.id,
            task_id=sample.task_id,
            record_key=sample.record_key,
            status=sample.status,
            latency_ms=sample.latency_ms,
            response_text=response.text if response else None,
            model=response.model if response else None,
            input_tokens=response.input_tokens if response else None,
            output_tokens=response.output_tokens if response else None,
            failure_category=failure.category if failure else None,
            failure_message=failure.message if failure else None,
        )
        for sample, response, failure in page
    ]
    return Page(
        items=items,
        page=PageMetadata(
            next_cursor=str(items[-1].id) if has_more and items else None,
            limit=limit,
        ),
    )


@router.get("/runs/{run_id}/aggregates", response_model=list[AggregateRead])
async def list_aggregates(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[AggregateRead]:
    """List aggregate metrics without confusing missing values with zero."""

    await _visible_run(project_id, run_id, principal, session)
    values = (
        await session.scalars(
            select(AggregateResultModel)
            .where(AggregateResultModel.run_id == run_id)
            .order_by(
                AggregateResultModel.metric_identifier,
                AggregateResultModel.metric_version,
                AggregateResultModel.slice_key,
            )
        )
    ).all()
    return [
        AggregateRead(
            metric_identifier=value.metric_identifier,
            metric_version=value.metric_version,
            slice_key=value.slice_key,
            value=value.value,
            total_count=value.total_count,
            available_count=value.available_count,
            missing_count=value.missing_count,
            failed_count=value.failed_count,
            pending_count=value.pending_count,
        )
        for value in values
    ]


@router.get("/runs/{run_id}/costs", response_model=list[CostSummaryRead])
async def summarize_costs(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[CostSummaryRead]:
    """Summarize estimated and actual ledger entries by currency."""

    await _visible_run(project_id, run_id, principal, session)
    values = (
        await session.scalars(
            select(CostRecordModel)
            .where(CostRecordModel.run_id == run_id)
            .order_by(CostRecordModel.id)
        )
    ).all()
    grouped: dict[str, tuple[Decimal, Decimal, int]] = {}
    for value in values:
        actual, estimated, count = grouped.get(value.currency, (Decimal("0"), Decimal("0"), 0))
        if value.estimated:
            estimated += value.amount
        else:
            actual += value.amount
        grouped[value.currency] = (actual, estimated, count + 1)
    return [
        CostSummaryRead(
            currency=currency,
            actual=actual,
            estimated=estimated,
            record_count=count,
        )
        for currency, (actual, estimated, count) in sorted(grouped.items())
    ]


@router.get("/runs/{run_id}/errors", response_model=list[ErrorSummaryRead])
async def summarize_errors(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[ErrorSummaryRead]:
    """Group sanitized failures without exposing provider payloads."""

    await _visible_run(project_id, run_id, principal, session)
    rows = (
        await session.execute(
            select(
                FailureRecordModel.category,
                FailureRecordModel.error_kind,
                func.count(FailureRecordModel.id),
            )
            .where(FailureRecordModel.run_id == run_id)
            .group_by(FailureRecordModel.category, FailureRecordModel.error_kind)
            .order_by(FailureRecordModel.category, FailureRecordModel.error_kind)
        )
    ).all()
    return [
        ErrorSummaryRead(category=category, error_kind=error_kind, count=count)
        for category, error_kind, count in rows
    ]


@router.get(
    "/samples/{sample_id}/retrieval-trace",
    response_model=RetrievalTraceRead,
)
async def get_retrieval_trace(
    project_id: uuid.UUID,
    sample_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RetrievalTraceRead:
    """Inspect a RAG retrieval trace for one visible sample."""

    await _visible_sample(project_id, sample_id, principal, session)
    trace = await session.scalar(
        select(RetrievalTraceModel).where(RetrievalTraceModel.sample_id == sample_id)
    )
    if trace is None:
        raise DomainError(ErrorCode.NOT_FOUND, "retrieval trace was not found")
    return RetrievalTraceRead(
        sample_id=sample_id,
        documents=trace.documents,
        retrieval_latency_ms=trace.retrieval_latency_ms,
        artifact_id=trace.artifact_id,
    )


@router.get(
    "/samples/{sample_id}/agent-trajectory",
    response_model=AgentTrajectoryRead,
)
async def get_agent_trajectory(
    project_id: uuid.UUID,
    sample_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> AgentTrajectoryRead:
    """Inspect a trajectory while preserving step order and tool evidence."""

    await _visible_sample(project_id, sample_id, principal, session)
    trajectory = await session.scalar(
        select(AgentTrajectoryModel).where(AgentTrajectoryModel.sample_id == sample_id)
    )
    if trajectory is None:
        raise DomainError(ErrorCode.NOT_FOUND, "agent trajectory was not found")
    return AgentTrajectoryRead(
        sample_id=sample_id,
        steps=trajectory.steps,
        step_count=trajectory.step_count,
        artifact_id=trajectory.artifact_id,
    )


@router.get("/runs/{run_id}/events")
async def stream_run_progress(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> StreamingResponse:
    """Stream durable run snapshots as server-sent events."""

    await _visible_run(project_id, run_id, principal, session)
    terminal = {"cancelled", "completed", "completed_with_errors", "failed"}

    async def events() -> AsyncIterator[str]:
        last_version = -1
        while not await request.is_disconnected():
            model = await session.scalar(
                select(EvaluationRunModel).where(
                    EvaluationRunModel.organization_id == principal.organization_id,
                    EvaluationRunModel.project_id == project_id,
                    EvaluationRunModel.id == run_id,
                )
            )
            if model is None:
                return
            if model.version_stamp != last_version:
                payload = _run_model_read(model).model_dump(mode="json")
                yield (
                    f"id: {model.version_stamp}\nevent: run.progress\n"
                    f"data: {json.dumps(payload)}\n\n"
                )
                last_version = model.version_stamp
            if model.state in terminal:
                return
            await asyncio.sleep(1)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _visible_run(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> EvaluationRun:
    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    run = await SqlExperimentRepository(session).get_run(
        principal.organization_id,
        project_id,
        run_id,
    )
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    return run


async def _visible_sample(
    project_id: uuid.UUID,
    sample_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> EvaluationSampleModel:
    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    sample = await session.scalar(
        select(EvaluationSampleModel).where(
            EvaluationSampleModel.organization_id == principal.organization_id,
            EvaluationSampleModel.project_id == project_id,
            EvaluationSampleModel.id == sample_id,
        )
    )
    if sample is None:
        raise DomainError(ErrorCode.NOT_FOUND, "evaluation sample was not found")
    return sample
