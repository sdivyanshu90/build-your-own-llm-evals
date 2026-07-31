"""Pairwise, judge, statistical comparison, report, slice, and gate endpoints."""

from __future__ import annotations

import hashlib
import statistics
import uuid
from collections import Counter, defaultdict
from decimal import Decimal

from eval_platform_application.comparisons import SampleMetric, compare_metric
from eval_platform_application.gates import evaluate_gate
from eval_platform_application.reporting import (
    comparison_csv,
    comparison_html,
    comparison_json,
    comparison_markdown,
)
from eval_platform_domain.auth import Action, authorize
from eval_platform_domain.canonicalization import canonical_bytes
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.ids import new_uuid7
from eval_platform_evaluators.pairwise import balanced_pair_assignments
from eval_platform_infrastructure.analysis_models import (
    ComparisonModel,
    JudgeConfigurationModel,
    JudgeResultModel,
    PairAssignmentModel,
    PairDesignModel,
    RubricVersionModel,
    SliceDefinitionModel,
)
from eval_platform_infrastructure.audit import append_audit_event
from eval_platform_infrastructure.models import AuditEventModel
from eval_platform_infrastructure.run_models import (
    EvaluationRunModel,
    EvaluationSampleModel,
    EvaluationTaskModel,
    ExperimentModel,
    MetricResultModel,
)
from eval_platform_schemas.analysis import (
    AuditEventRead,
    ComparisonCreate,
    ComparisonRead,
    GateConfiguration,
    GateResult,
    JudgeConfigurationCreate,
    JudgeConfigurationRead,
    JudgmentCreate,
    JudgmentRead,
    MetricComparisonRead,
    PairAggregateRead,
    PairAssignmentRead,
    PairDesignCreate,
    PairDesignRead,
    RubricCreate,
    RubricRead,
    SliceCreate,
    SliceRead,
)
from eval_platform_schemas.common import Page, PageMetadata
from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select

from eval_platform_api.dependencies import PrincipalDependency, SessionDependency

router = APIRouter(prefix="/api/v1/projects/{project_id}", tags=["analysis"])


@router.post("/rubrics", response_model=RubricRead, status_code=status.HTTP_201_CREATED)
async def create_rubric(
    project_id: uuid.UUID,
    body: RubricCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> RubricRead:
    """Create an immutable rubric version."""

    _authorize(principal, Action.CONFIG_WRITE, project_id)
    identifier_count = len({dimension.identifier for dimension in body.dimensions})
    if identifier_count != len(body.dimensions):
        raise DomainError(ErrorCode.VALIDATION, "rubric dimension identifiers must be unique")
    content_hash = _hash(body.model_dump(mode="json"))
    model = RubricVersionModel(
        organization_id=principal.organization_id,
        project_id=project_id,
        identifier=body.identifier,
        version=body.version,
        title=body.title,
        instructions=body.instructions,
        dimensions=[dimension.model_dump(mode="json") for dimension in body.dimensions],
        content_hash=content_hash,
    )
    session.add(model)
    await session.flush()
    await _audit(session, request, principal, project_id, "rubric.create", "rubric", model.id)
    return _rubric_read(model)


@router.get("/rubrics", response_model=list[RubricRead])
async def list_rubrics(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[RubricRead]:
    """List immutable rubric versions."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    values = (
        await session.scalars(
            select(RubricVersionModel)
            .where(
                RubricVersionModel.organization_id == principal.organization_id,
                RubricVersionModel.project_id == project_id,
            )
            .order_by(RubricVersionModel.id)
            .limit(limit)
        )
    ).all()
    return [_rubric_read(value) for value in values]


@router.post(
    "/judge-configurations",
    response_model=JudgeConfigurationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_judge_configuration(
    project_id: uuid.UUID,
    body: JudgeConfigurationCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> JudgeConfigurationRead:
    """Create a secret-free immutable judge policy."""

    _authorize(principal, Action.CONFIG_WRITE, project_id)
    rubric = await session.scalar(
        select(RubricVersionModel).where(
            RubricVersionModel.organization_id == principal.organization_id,
            RubricVersionModel.project_id == project_id,
            RubricVersionModel.id == body.rubric_id,
        )
    )
    if rubric is None:
        raise DomainError(ErrorCode.NOT_FOUND, "rubric was not found")
    configuration = body.model_dump(mode="json")
    model = JudgeConfigurationModel(
        organization_id=principal.organization_id,
        project_id=project_id,
        rubric_id=body.rubric_id,
        identifier=body.identifier,
        version=body.version,
        configuration=configuration,
        content_hash=_hash(configuration),
    )
    session.add(model)
    await session.flush()
    await _audit(
        session,
        request,
        principal,
        project_id,
        "judge_configuration.create",
        "judge_configuration",
        model.id,
    )
    return _judge_configuration_read(model)


@router.get("/judge-configurations", response_model=list[JudgeConfigurationRead])
async def list_judge_configurations(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[JudgeConfigurationRead]:
    """List judge configurations without provider secrets."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    values = (
        await session.scalars(
            select(JudgeConfigurationModel)
            .where(
                JudgeConfigurationModel.organization_id == principal.organization_id,
                JudgeConfigurationModel.project_id == project_id,
            )
            .order_by(JudgeConfigurationModel.id)
            .limit(limit)
        )
    ).all()
    return [_judge_configuration_read(value) for value in values]


@router.post(
    "/pair-designs",
    response_model=PairDesignRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pair_design(
    project_id: uuid.UUID,
    body: PairDesignCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> PairDesignRead:
    """Create deterministic, balanced, optionally reversed pair assignments."""

    _authorize(principal, Action.CONFIG_WRITE, project_id)
    design_id = new_uuid7()
    try:
        assignments = balanced_pair_assignments(
            design_id=design_id,
            record_keys=body.record_keys,
            variant_ids=body.variant_ids,
            judge_slots=body.judge_slots,
            repetitions=body.repetitions,
            seed=body.seed,
            sample_size=body.sample_size,
            reversed_duplicates=body.reversed_duplicates,
        )
    except ValueError as error:
        raise DomainError(ErrorCode.VALIDATION, str(error)) from error
    design = PairDesignModel(
        id=design_id,
        organization_id=principal.organization_id,
        project_id=project_id,
        name=body.name,
        variant_ids=body.variant_ids,
        seed=Decimal(body.seed),
        judge_slots=body.judge_slots,
        repetitions=body.repetitions,
        reversed_duplicates=body.reversed_duplicates,
        assignment_count=len(assignments),
    )
    session.add(design)
    session.add_all(
        [
            PairAssignmentModel(
                id=assignment.id,
                organization_id=principal.organization_id,
                project_id=project_id,
                design_id=design_id,
                record_key=assignment.record_key,
                variant_a_id=assignment.variant_a_id,
                variant_b_id=assignment.variant_b_id,
                judge_slot=assignment.judge_slot,
                repetition=assignment.repetition,
                orientation=assignment.orientation,
                order_seed=Decimal(assignment.order_seed),
                reverse_of=assignment.reverse_of,
            )
            for assignment in assignments
        ]
    )
    await session.flush()
    await _audit(
        session,
        request,
        principal,
        project_id,
        "pair_design.create",
        "pair_design",
        design_id,
        {"assignment_count": len(assignments)},
    )
    return PairDesignRead(
        id=design_id,
        project_id=project_id,
        name=body.name,
        seed=body.seed,
        assignment_count=len(assignments),
        reversed_duplicates=body.reversed_duplicates,
        assignments=[_assignment_read(assignment) for assignment in assignments],
    )


@router.get("/pair-designs/{design_id}", response_model=PairDesignRead)
async def get_pair_design(
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    include_assignments: bool = True,
) -> PairDesignRead:
    """Retrieve a tenant-scoped pair design and opaque assignment labels."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    design = await _design(session, principal.organization_id, project_id, design_id)
    assignments: list[PairAssignmentModel] = []
    if include_assignments:
        assignments = list(
            (
                await session.scalars(
                    select(PairAssignmentModel)
                    .where(PairAssignmentModel.design_id == design_id)
                    .order_by(PairAssignmentModel.id)
                )
            ).all()
        )
    return PairDesignRead(
        id=design.id,
        project_id=design.project_id,
        name=design.name,
        seed=int(design.seed),
        assignment_count=design.assignment_count,
        reversed_duplicates=design.reversed_duplicates,
        assignments=[_assignment_model_read(value) for value in assignments],
    )


@router.get("/pair-designs", response_model=list[PairDesignRead])
async def list_pair_designs(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PairDesignRead]:
    """List pair-design summaries without materializing assignments."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    designs = (
        await session.scalars(
            select(PairDesignModel)
            .where(
                PairDesignModel.organization_id == principal.organization_id,
                PairDesignModel.project_id == project_id,
            )
            .order_by(PairDesignModel.id)
            .limit(limit)
        )
    ).all()
    return [
        PairDesignRead(
            id=design.id,
            project_id=design.project_id,
            name=design.name,
            seed=int(design.seed),
            assignment_count=design.assignment_count,
            reversed_duplicates=design.reversed_duplicates,
        )
        for design in designs
    ]


@router.post(
    "/pair-assignments/{assignment_id}/judgments",
    response_model=JudgmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_judgment(
    project_id: uuid.UUID,
    assignment_id: uuid.UUID,
    body: JudgmentCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> JudgmentRead:
    """Append a validated human or LLM judgment once per judge and assignment."""

    _authorize(principal, Action.JUDGMENT_WRITE, project_id)
    assignment = await session.scalar(
        select(PairAssignmentModel).where(
            PairAssignmentModel.organization_id == principal.organization_id,
            PairAssignmentModel.project_id == project_id,
            PairAssignmentModel.id == assignment_id,
        )
    )
    if assignment is None:
        raise DomainError(ErrorCode.NOT_FOUND, "pair assignment was not found")
    model = JudgeResultModel(
        organization_id=principal.organization_id,
        project_id=project_id,
        assignment_id=assignment_id,
        **body.model_dump(mode="python"),
        usage={},
    )
    session.add(model)
    await session.flush()
    await _audit(
        session,
        request,
        principal,
        project_id,
        "judgment.create",
        "pair_assignment",
        assignment_id,
        {"judge_kind": body.judge_kind, "verdict": body.verdict},
    )
    return _judgment_read(model)


@router.get("/pair-designs/{design_id}/aggregate", response_model=PairAggregateRead)
async def pair_aggregate(
    project_id: uuid.UUID,
    design_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> PairAggregateRead:
    """Aggregate pair outcomes, abstentions, disagreement, and display position."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    design = await _design(session, principal.organization_id, project_id, design_id)
    rows = (
        await session.execute(
            select(PairAssignmentModel, JudgeResultModel)
            .join(
                JudgeResultModel,
                JudgeResultModel.assignment_id == PairAssignmentModel.id,
            )
            .where(PairAssignmentModel.design_id == design_id)
        )
    ).all()
    counts = Counter(result.verdict for _assignment, result in rows)
    usable = counts["A"] + counts["B"] + counts["tie"]
    decisive = counts["A"] + counts["B"]
    by_assignment: dict[uuid.UUID, Counter[str]] = defaultdict(Counter)
    for assignment, result in rows:
        by_assignment[assignment.id][result.verdict] += 1
    disagreement_values = []
    for assignment_counts in by_assignment.values():
        assignment_usable = sum(assignment_counts[verdict] for verdict in ("A", "B", "tie"))
        if assignment_usable:
            disagreement_values.append(
                1
                - max(assignment_counts[verdict] for verdict in ("A", "B", "tie"))
                / assignment_usable
            )
    return PairAggregateRead(
        assignment_count=design.assignment_count,
        judgment_count=len(rows),
        wins_a=counts["A"],
        wins_b=counts["B"],
        ties=counts["tie"],
        abstentions=counts["abstain"],
        usable_count=usable,
        tie_adjusted_a_win_rate=((counts["A"] + 0.5 * counts["tie"]) / usable if usable else None),
        disagreement_rate=(statistics.fmean(disagreement_values) if disagreement_values else None),
        position_a_win_rate=counts["A"] / decisive if decisive else None,
    )


@router.post(
    "/comparisons",
    response_model=ComparisonRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_comparison(
    project_id: uuid.UUID,
    body: ComparisonCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> ComparisonRead:
    """Create and persist a reproducible record-paired run comparison."""

    _authorize(principal, Action.ANALYSIS_WRITE, project_id)
    baseline_run = await _run(session, principal.organization_id, project_id, body.baseline_run_id)
    candidate_run = await _run(
        session, principal.organization_id, project_id, body.candidate_run_id
    )
    baseline_experiment = await session.get(ExperimentModel, baseline_run.experiment_id)
    candidate_experiment = await session.get(ExperimentModel, candidate_run.experiment_id)
    if baseline_experiment is None or candidate_experiment is None:
        raise DomainError(ErrorCode.NOT_FOUND, "comparison experiment was not found")
    compatible = baseline_experiment.dataset_version_id == candidate_experiment.dataset_version_id
    if not compatible and not body.allow_dataset_intersection:
        raise DomainError(
            ErrorCode.CONFLICT,
            "dataset versions differ; explicitly allow intersection-only analysis",
        )
    grouped = await _metric_samples(
        session,
        body.baseline_run_id,
        body.candidate_run_id,
        set(body.metric_identifiers),
    )
    metric_keys = sorted(set(grouped[body.baseline_run_id]) & set(grouped[body.candidate_run_id]))
    if not metric_keys:
        raise DomainError(ErrorCode.VALIDATION, "runs have no comparable scalar metrics")
    metrics = [
        compare_metric(
            metric_identifier=identifier,
            metric_version=version,
            baseline=grouped[body.baseline_run_id][(identifier, version)],
            candidate=grouped[body.candidate_run_id][(identifier, version)],
            confidence=body.confidence,
            bootstrap_method=body.bootstrap_method,
            bootstrap_resamples=body.bootstrap_resamples,
            test=body.test,
            seed=body.seed,
            missing_data_policy=body.missing_data_policy,
            practical_difference=body.practical_difference,
            top_changed_examples=body.top_changed_examples,
        )
        for identifier, version in metric_keys
    ]
    from eval_platform_statistics.multiplicity import adjust_p_values

    adjusted = adjust_p_values(
        {
            f"{metric.metric_identifier}@{metric.metric_version}": metric.p_value
            for metric in metrics
        },
        method="holm",
    )
    metrics = [
        metric.model_copy(
            update={
                "adjusted_p_value": adjusted[f"{metric.metric_identifier}@{metric.metric_version}"]
            }
        )
        for metric in metrics
    ]
    limitations = [
        "Provider-side nondeterminism can prevent bit-for-bit reproduction.",
        "P-values do not measure practical importance or probability that a model is better.",
    ]
    if not compatible:
        limitations.append(
            "Dataset versions differ; only overlapping record/repetition identities were paired."
        )
    comparison_id = new_uuid7()
    read = ComparisonRead(
        id=comparison_id,
        project_id=project_id,
        baseline_run_id=body.baseline_run_id,
        candidate_run_id=body.candidate_run_id,
        baseline_dataset_version_id=baseline_experiment.dataset_version_id,
        candidate_dataset_version_id=candidate_experiment.dataset_version_id,
        dataset_compatible=compatible,
        intersection_only=not compatible,
        configuration=body,
        metrics=metrics,
        limitations=limitations,
    )
    session.add(
        ComparisonModel(
            id=comparison_id,
            organization_id=principal.organization_id,
            project_id=project_id,
            baseline_run_id=body.baseline_run_id,
            candidate_run_id=body.candidate_run_id,
            baseline_dataset_version_id=baseline_experiment.dataset_version_id,
            candidate_dataset_version_id=candidate_experiment.dataset_version_id,
            configuration=body.model_dump(mode="json"),
            results=[metric.model_dump(mode="json") for metric in metrics],
            limitations=limitations,
        )
    )
    await _audit(
        session,
        request,
        principal,
        project_id,
        "comparison.create",
        "comparison",
        comparison_id,
        {"metric_count": len(metrics), "intersection_only": not compatible},
    )
    return read


@router.get("/comparisons/{comparison_id}", response_model=ComparisonRead)
async def get_comparison(
    project_id: uuid.UUID,
    comparison_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> ComparisonRead:
    """Retrieve one immutable stored comparison."""

    _authorize(principal, Action.RUN_READ, project_id)
    model = await _comparison(session, principal.organization_id, project_id, comparison_id)
    return _comparison_read(model)


@router.get("/comparisons", response_model=list[ComparisonRead])
async def list_comparisons(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ComparisonRead]:
    """List recent immutable comparison reports."""

    _authorize(principal, Action.RUN_READ, project_id)
    values = (
        await session.scalars(
            select(ComparisonModel)
            .where(
                ComparisonModel.organization_id == principal.organization_id,
                ComparisonModel.project_id == project_id,
            )
            .order_by(ComparisonModel.id.desc())
            .limit(limit)
        )
    ).all()
    return [_comparison_read(value) for value in values]


@router.get("/comparisons/{comparison_id}/report")
async def export_comparison_report(
    project_id: uuid.UUID,
    comparison_id: uuid.UUID,
    format: str,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> Response:
    """Export JSON, safe CSV, Markdown, or printable HTML."""

    _authorize(principal, Action.REPORT_EXPORT, project_id)
    comparison = _comparison_read(
        await _comparison(session, principal.organization_id, project_id, comparison_id)
    )
    renderers = {
        "json": (comparison_json, "application/json"),
        "csv": (comparison_csv, "text/csv; charset=utf-8"),
        "markdown": (comparison_markdown, "text/markdown; charset=utf-8"),
        "html": (comparison_html, "text/html; charset=utf-8"),
    }
    if format not in renderers:
        raise DomainError(
            ErrorCode.VALIDATION,
            "report format must be json, csv, markdown, or html",
        )
    renderer, media_type = renderers[format]
    return Response(renderer(comparison), media_type=media_type)


@router.post("/comparisons/{comparison_id}/gate", response_model=GateResult)
async def evaluate_comparison_gate(
    project_id: uuid.UUID,
    comparison_id: uuid.UUID,
    body: GateConfiguration,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> GateResult:
    """Evaluate a versioned quality gate against a stored comparison."""

    _authorize(principal, Action.ANALYSIS_WRITE, project_id)
    comparison = _comparison_read(
        await _comparison(session, principal.organization_id, project_id, comparison_id)
    )
    result = evaluate_gate(body, comparison)
    await _audit(
        session,
        request,
        principal,
        project_id,
        "quality_gate.evaluate",
        "comparison",
        comparison_id,
        {"passed": result.passed, "rule_count": len(result.rules)},
    )
    return result


@router.post("/slices", response_model=SliceRead, status_code=status.HTTP_201_CREATED)
async def create_slice(
    project_id: uuid.UUID,
    body: SliceCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> SliceRead:
    """Create an immutable safe declarative slice."""

    _authorize(principal, Action.CONFIG_WRITE, project_id)
    _validate_slice_predicate(body.predicate)
    if body.parent_slice_id is not None:
        parent = await session.scalar(
            select(SliceDefinitionModel.id).where(
                SliceDefinitionModel.organization_id == principal.organization_id,
                SliceDefinitionModel.project_id == project_id,
                SliceDefinitionModel.id == body.parent_slice_id,
            )
        )
        if parent is None:
            raise DomainError(ErrorCode.NOT_FOUND, "parent slice was not found")
    model = SliceDefinitionModel(
        organization_id=principal.organization_id,
        project_id=project_id,
        **body.model_dump(mode="python"),
        content_hash=_hash(body.model_dump(mode="json")),
    )
    session.add(model)
    await session.flush()
    await _audit(session, request, principal, project_id, "slice.create", "slice", model.id)
    return _slice_read(model)


@router.get("/slices", response_model=list[SliceRead])
async def list_slices(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[SliceRead]:
    """List safe versioned slice definitions."""

    _authorize(principal, Action.CONFIG_READ, project_id)
    values = (
        await session.scalars(
            select(SliceDefinitionModel)
            .where(
                SliceDefinitionModel.organization_id == principal.organization_id,
                SliceDefinitionModel.project_id == project_id,
            )
            .order_by(SliceDefinitionModel.id)
        )
    ).all()
    return [_slice_read(value) for value in values]


@router.get("/audit-events", response_model=Page[AuditEventRead])
async def list_audit_events(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=100, ge=1, le=200),
    after: uuid.UUID | None = None,
) -> Page[AuditEventRead]:
    """List project audit events for authorized administrators."""

    _authorize(principal, Action.AUDIT_READ, project_id)
    statement = (
        select(AuditEventModel)
        .where(
            AuditEventModel.organization_id == principal.organization_id,
            AuditEventModel.project_id == project_id,
        )
        .order_by(AuditEventModel.id)
        .limit(limit + 1)
    )
    if after is not None:
        statement = statement.where(AuditEventModel.id > after)
    values = list((await session.scalars(statement)).all())
    has_more = len(values) > limit
    values = values[:limit]
    return Page(
        items=[
            AuditEventRead(
                id=value.id,
                sequence=value.sequence,
                project_id=value.project_id,
                actor_subject=value.actor_subject,
                action=value.action,
                target_type=value.target_type,
                target_id=value.target_id,
                outcome=value.outcome,
                request_id=value.request_id,
                summary=value.summary,
                previous_hash=value.previous_hash,
                event_hash=value.event_hash,
            )
            for value in values
        ],
        page=PageMetadata(
            next_cursor=str(values[-1].id) if has_more and values else None,
            limit=limit,
        ),
    )


async def _metric_samples(
    session: SessionDependency,
    baseline_run_id: uuid.UUID,
    candidate_run_id: uuid.UUID,
    requested: set[str],
) -> dict[
    uuid.UUID,
    dict[tuple[str, str], dict[str, SampleMetric]],
]:
    statement = (
        select(
            MetricResultModel.run_id,
            MetricResultModel.metric_identifier,
            MetricResultModel.metric_version,
            MetricResultModel.status,
            MetricResultModel.scalar,
            EvaluationSampleModel.record_key,
            EvaluationTaskModel.repetition,
        )
        .join(
            EvaluationSampleModel,
            EvaluationSampleModel.id == MetricResultModel.sample_id,
        )
        .join(EvaluationTaskModel, EvaluationTaskModel.id == EvaluationSampleModel.task_id)
        .where(MetricResultModel.run_id.in_([baseline_run_id, candidate_run_id]))
    )
    if requested:
        statement = statement.where(MetricResultModel.metric_identifier.in_(requested))
    rows = (await session.execute(statement)).all()
    grouped: dict[
        uuid.UUID,
        dict[tuple[str, str], dict[str, SampleMetric]],
    ] = defaultdict(lambda: defaultdict(dict))
    for run_id, identifier, version, result_status, scalar, record_key, repetition in rows:
        analysis_id = f"{record_key}#rep={repetition}"
        grouped[run_id][(identifier, version)][analysis_id] = SampleMetric(
            analysis_id,
            result_status,
            scalar,
        )
    return grouped


async def _design(
    session: SessionDependency,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    design_id: uuid.UUID,
) -> PairDesignModel:
    design = await session.scalar(
        select(PairDesignModel).where(
            PairDesignModel.organization_id == organization_id,
            PairDesignModel.project_id == project_id,
            PairDesignModel.id == design_id,
        )
    )
    if design is None:
        raise DomainError(ErrorCode.NOT_FOUND, "pair design was not found")
    return design


async def _run(
    session: SessionDependency,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> EvaluationRunModel:
    run = await session.scalar(
        select(EvaluationRunModel).where(
            EvaluationRunModel.organization_id == organization_id,
            EvaluationRunModel.project_id == project_id,
            EvaluationRunModel.id == run_id,
        )
    )
    if run is None:
        raise DomainError(ErrorCode.NOT_FOUND, "evaluation run was not found")
    return run


async def _comparison(
    session: SessionDependency,
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    comparison_id: uuid.UUID,
) -> ComparisonModel:
    model = await session.scalar(
        select(ComparisonModel).where(
            ComparisonModel.organization_id == organization_id,
            ComparisonModel.project_id == project_id,
            ComparisonModel.id == comparison_id,
        )
    )
    if model is None:
        raise DomainError(ErrorCode.NOT_FOUND, "comparison was not found")
    return model


def _comparison_read(model: ComparisonModel) -> ComparisonRead:
    configuration = ComparisonCreate.model_validate(model.configuration)
    compatible = model.baseline_dataset_version_id == model.candidate_dataset_version_id
    return ComparisonRead(
        id=model.id,
        project_id=model.project_id,
        baseline_run_id=model.baseline_run_id,
        candidate_run_id=model.candidate_run_id,
        baseline_dataset_version_id=model.baseline_dataset_version_id,
        candidate_dataset_version_id=model.candidate_dataset_version_id,
        dataset_compatible=compatible,
        intersection_only=not compatible,
        configuration=configuration,
        metrics=[MetricComparisonRead.model_validate(metric) for metric in model.results],
        limitations=model.limitations,
    )


def _rubric_read(model: RubricVersionModel) -> RubricRead:
    return RubricRead(
        id=model.id,
        project_id=model.project_id,
        identifier=model.identifier,
        version=model.version,
        title=model.title,
        instructions=model.instructions,
        dimensions=model.dimensions,
        content_hash=model.content_hash,
    )


def _judge_configuration_read(model: JudgeConfigurationModel) -> JudgeConfigurationRead:
    return JudgeConfigurationRead.model_validate(
        {
            **model.configuration,
            "id": model.id,
            "project_id": model.project_id,
            "content_hash": model.content_hash,
        }
    )


def _assignment_read(assignment: object) -> PairAssignmentRead:
    from eval_platform_evaluators.pairwise import PairAssignment

    if not isinstance(assignment, PairAssignment):
        raise TypeError("expected pair assignment")
    return PairAssignmentRead(
        id=assignment.id,
        record_key=assignment.record_key,
        candidate_a_id=f"blind:{assignment.id}:A",
        candidate_b_id=f"blind:{assignment.id}:B",
        judge_slot=assignment.judge_slot,
        repetition=assignment.repetition,
        orientation=assignment.orientation,
        reverse_of=assignment.reverse_of,
    )


def _assignment_model_read(model: PairAssignmentModel) -> PairAssignmentRead:
    return PairAssignmentRead(
        id=model.id,
        record_key=model.record_key,
        candidate_a_id=f"blind:{model.id}:A",
        candidate_b_id=f"blind:{model.id}:B",
        judge_slot=model.judge_slot,
        repetition=model.repetition,
        orientation=model.orientation,
        reverse_of=model.reverse_of,
    )


def _judgment_read(model: JudgeResultModel) -> JudgmentRead:
    return JudgmentRead(
        id=model.id,
        assignment_id=model.assignment_id,
        judge_kind=model.judge_kind,
        judge_identifier=model.judge_identifier,
        verdict=model.verdict,
        confidence=model.confidence,
        scores=model.scores,
        evidence=model.evidence,
        justification=model.justification,
        abstention_reason=model.abstention_reason,
        schema_version="judge-response/1",
    )


def _slice_read(model: SliceDefinitionModel) -> SliceRead:
    return SliceRead(
        id=model.id,
        project_id=model.project_id,
        identifier=model.identifier,
        version=model.version,
        description=model.description,
        predicate=model.predicate,
        parent_slice_id=model.parent_slice_id,
        content_hash=model.content_hash,
    )


def _validate_slice_predicate(predicate: dict[str, object]) -> None:
    allowed = {"field", "operator", "value", "values", "minimum", "maximum"}
    unknown = set(predicate) - allowed
    if unknown:
        raise DomainError(
            ErrorCode.VALIDATION,
            "slice predicate contains unsupported keys",
            details={"keys": sorted(unknown)},
        )
    if "field" not in predicate or "operator" not in predicate:
        raise DomainError(
            ErrorCode.VALIDATION,
            "slice predicate requires field and operator",
        )
    if predicate["operator"] not in {
        "equals",
        "not_equals",
        "in",
        "contains",
        "range",
        "exists",
    }:
        raise DomainError(ErrorCode.VALIDATION, "slice operator is unsupported")


def _hash(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _authorize(principal: PrincipalDependency, action: Action, project_id: uuid.UUID) -> None:
    authorize(
        principal,
        action,
        organization_id=principal.organization_id,
        project_id=project_id,
    )


async def _audit(
    session: SessionDependency,
    request: Request,
    principal: PrincipalDependency,
    project_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    summary: dict[str, object] | None = None,
) -> None:
    await append_audit_event(
        session,
        organization_id=principal.organization_id,
        project_id=project_id,
        actor_subject=principal.subject,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome="succeeded",
        request_id=request.state.request_id,
        summary=summary,
    )
