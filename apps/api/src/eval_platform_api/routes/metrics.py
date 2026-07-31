"""Metric catalog and run aggregate endpoints."""

from __future__ import annotations

import uuid

from eval_platform_domain.auth import Action, authorize
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_infrastructure.run_models import EvaluationRunModel, MetricResultModel
from eval_platform_metrics.registry import builtin_registry
from eval_platform_schemas.metrics import MetricAggregateRead, MetricDefinitionRead
from fastapi import APIRouter
from sqlalchemy import func, select

from eval_platform_api.dependencies import PrincipalDependency, SessionDependency

router = APIRouter(tags=["metrics"])


@router.get("/api/v1/metrics", response_model=list[MetricDefinitionRead])
async def list_metric_definitions(
    principal: PrincipalDependency,
) -> list[MetricDefinitionRead]:
    """List built-in versioned metric contracts."""

    del principal
    return [
        MetricDefinitionRead(
            identifier=definition.identifier,
            name=definition.name,
            version=definition.version,
            description=definition.description,
            task_types=sorted(definition.task_types),
            required_fields=sorted(definition.required_fields),
            output_schema=definition.output_schema,
            direction=definition.direction,
            minimum=definition.minimum,
            maximum=definition.maximum,
            reference_required=definition.reference_required,
            external_model_required=definition.external_model_required,
            determinism=definition.determinism,
            aggregation=definition.aggregation,
            failure_behavior=definition.failure_behavior,
            configuration_schema=definition.configuration_schema,
            computational_cost=definition.computational_cost,
            monetary_cost=definition.monetary_cost,
        )
        for definition in builtin_registry().definitions()
    ]


@router.get(
    "/api/v1/projects/{project_id}/runs/{run_id}/metrics",
    response_model=list[MetricAggregateRead],
)
async def aggregate_metrics(
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[MetricAggregateRead]:
    """Aggregate scalar metrics while retaining all failed/missing/pending samples."""

    authorize(
        principal,
        Action.RUN_READ,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
    run = await session.scalar(
        select(EvaluationRunModel).where(
            EvaluationRunModel.organization_id == principal.organization_id,
            EvaluationRunModel.project_id == project_id,
            EvaluationRunModel.id == run_id,
        )
    )
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "run was not found")
    rows = (
        await session.execute(
            select(
                MetricResultModel.metric_identifier,
                MetricResultModel.metric_version,
                func.avg(MetricResultModel.scalar).filter(
                    MetricResultModel.status == "succeeded",
                    MetricResultModel.scalar.is_not(None),
                ),
                func.count().filter(
                    MetricResultModel.status == "succeeded",
                    MetricResultModel.scalar.is_not(None),
                ),
                func.count().filter(MetricResultModel.status == "missing"),
                func.count().filter(MetricResultModel.status == "failed"),
            )
            .where(
                MetricResultModel.organization_id == principal.organization_id,
                MetricResultModel.project_id == project_id,
                MetricResultModel.run_id == run_id,
            )
            .group_by(
                MetricResultModel.metric_identifier,
                MetricResultModel.metric_version,
            )
            .order_by(MetricResultModel.metric_identifier)
        )
    ).all()
    settled = run.succeeded_tasks + run.failed_tasks + run.cancelled_tasks
    pending = run.total_tasks - settled
    return [
        MetricAggregateRead(
            metric_identifier=identifier,
            metric_version=version,
            value=float(value) if value is not None else None,
            total_count=run.total_tasks,
            available_count=int(available),
            missing_count=int(missing) + run.cancelled_tasks,
            failed_count=int(metric_failed) + run.failed_tasks,
            pending_count=pending,
        )
        for identifier, version, value, available, missing, metric_failed in rows
    ]
