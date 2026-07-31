"""Run the deterministic provider end to end and print a compact result report."""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from eval_platform_application.comparisons import SampleMetric, compare_metric
from eval_platform_application.experiments import ExperimentService
from eval_platform_application.gates import evaluate_gate
from eval_platform_application.reporting import comparison_markdown
from eval_platform_domain.auth import Principal, ProjectRole
from eval_platform_domain.ids import new_uuid7
from eval_platform_domain.money import Money
from eval_platform_infrastructure.analysis_models import ComparisonModel
from eval_platform_infrastructure.database import create_engine, create_session_factory
from eval_platform_infrastructure.models import ArtifactModel
from eval_platform_infrastructure.object_store import S3ObjectStore
from eval_platform_infrastructure.run_models import (
    EvaluationSampleModel,
    MetricResultModel,
    ModelResponseModel,
)
from eval_platform_infrastructure.run_repository import SqlExperimentRepository
from eval_platform_infrastructure.settings import Settings
from eval_platform_schemas.analysis import (
    ComparisonCreate,
    ComparisonRead,
    GateConfiguration,
    MissingDataPolicy,
)
from eval_platform_worker.tasks import _execute_run
from sqlalchemy import select

from eval_platform_api.seed import DEMO_ORGANIZATION_ID, DEMO_PROJECT_ID, seed


def _dependency_lock_hash() -> str:
    lock_path = Path("uv.lock")
    return (
        hashlib.sha256(lock_path.read_bytes()).hexdigest()
        if lock_path.exists()
        else "container-image"
    )


async def run_demo() -> dict[str, Any]:
    """Run baseline and candidate systems, compare them, and persist a report."""

    seeded = await seed()
    version_id = uuid.UUID(seeded["dataset_version_id"])
    principal = Principal(
        subject="local-demo",
        organization_id=DEMO_ORGANIZATION_ID,
        project_id=DEMO_PROJECT_ID,
        role=ProjectRole.ADMIN,
    )
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    lock_hash = await asyncio.to_thread(_dependency_lock_hash)
    try:
        async with factory() as session:
            repository = SqlExperimentRepository(session)
            dataset_version = await repository.get_dataset_version(
                DEMO_ORGANIZATION_ID,
                DEMO_PROJECT_ID,
                version_id,
            )
            if dataset_version is None:
                raise RuntimeError("seeded dataset version was not found")
            service = ExperimentService(repository)
            baseline_experiment = await service.create_experiment(
                principal,
                project_id=DEMO_PROJECT_ID,
                dataset_version_id=version_id,
                provider={
                    "type": "fake",
                    "identifier": "fake/demo-v1",
                    "responses": {
                        "Answer concisely: What is the capital of France?": "Paris",
                        "Answer concisely: What is two plus two?": "4",
                        "Answer concisely: What is the chemical formula for water?": "H2O",
                    },
                },
                model="fake-model-v1",
                prompt_template="Answer concisely: {{ input }}",
                parameters={
                    "temperature": 0,
                    "max_output_tokens": 20,
                    "input_cost_per_million": "0",
                    "output_cost_per_million": "0",
                },
                suite={
                    "task_type": "qa",
                    "input_field": "question",
                    "reference_field": "answers",
                    "metrics": [
                        {"id": "language/exact-match", "configuration": {}},
                        {"id": "language/normalized-exact-match", "configuration": {}},
                        {"id": "operations/latency-ms", "configuration": {}},
                    ],
                },
                seed=20260729,
                application_version=settings.service_version,
                dependency_lock_hash=lock_hash,
            )
            baseline_creation = await service.create_run(
                principal,
                experiment=baseline_experiment,
                dataset_version=dataset_version,
                repetitions=1,
                budget_limit=Money(Decimal("1.00")),
            )
            baseline_run_id = baseline_creation.run.id
            await session.commit()

        await _execute_run(baseline_run_id, owner="local-demo-baseline")

        async with factory() as session:
            repository = SqlExperimentRepository(session)
            dataset_version = await repository.get_dataset_version(
                DEMO_ORGANIZATION_ID,
                DEMO_PROJECT_ID,
                version_id,
            )
            if dataset_version is None:
                raise RuntimeError("seeded dataset version was not found")
            service = ExperimentService(repository)
            candidate_experiment = await service.create_experiment(
                principal,
                project_id=DEMO_PROJECT_ID,
                dataset_version_id=version_id,
                provider={
                    "type": "fake",
                    "identifier": "fake/demo-candidate-v1",
                    "responses": {
                        "Answer concisely: What is the capital of France?": "Paris",
                        "Answer concisely: What is two plus two?": "4",
                        "Answer concisely: What is the chemical formula for water?": "HHO",
                    },
                },
                model="fake-model-candidate-v1",
                prompt_template="Answer concisely: {{ input }}",
                parameters={
                    "temperature": 0,
                    "max_output_tokens": 20,
                    "input_cost_per_million": "0",
                    "output_cost_per_million": "0",
                },
                suite=baseline_experiment.suite,
                seed=20260730,
                application_version=settings.service_version,
                dependency_lock_hash=lock_hash,
            )
            candidate_creation = await service.create_run(
                principal,
                experiment=candidate_experiment,
                dataset_version=dataset_version,
                repetitions=1,
                budget_limit=Money(Decimal("1.00")),
            )
            candidate_run_id = candidate_creation.run.id
            await session.commit()

        await _execute_run(candidate_run_id, owner="local-demo-candidate")

        async with factory() as session:
            repository = SqlExperimentRepository(session)
            baseline_run = await repository.get_run(
                DEMO_ORGANIZATION_ID,
                DEMO_PROJECT_ID,
                baseline_run_id,
            )
            candidate_run = await repository.get_run(
                DEMO_ORGANIZATION_ID,
                DEMO_PROJECT_ID,
                candidate_run_id,
            )
            if baseline_run is None or candidate_run is None:
                raise RuntimeError("demonstration runs were not found")
            samples = (
                await session.scalars(
                    select(EvaluationSampleModel).where(
                        EvaluationSampleModel.run_id.in_([baseline_run_id, candidate_run_id])
                    )
                )
            ).all()
            responses = (
                await session.scalars(
                    select(ModelResponseModel)
                    .join(
                        EvaluationSampleModel,
                        EvaluationSampleModel.id == ModelResponseModel.sample_id,
                    )
                    .where(EvaluationSampleModel.run_id.in_([baseline_run_id, candidate_run_id]))
                )
            ).all()
            metric_rows = (
                await session.execute(
                    select(MetricResultModel, EvaluationSampleModel.record_key)
                    .join(
                        EvaluationSampleModel,
                        EvaluationSampleModel.id == MetricResultModel.sample_id,
                    )
                    .where(
                        MetricResultModel.run_id.in_([baseline_run_id, candidate_run_id]),
                        MetricResultModel.metric_identifier == "language/exact-match",
                    )
                )
            ).all()
            by_run: dict[uuid.UUID, dict[str, SampleMetric]] = {
                baseline_run_id: {},
                candidate_run_id: {},
            }
            for metric_row, record_key in metric_rows:
                by_run[metric_row.run_id][record_key] = SampleMetric(
                    record_id=record_key,
                    status=metric_row.status,
                    value=metric_row.scalar,
                )
            configuration = ComparisonCreate(
                baseline_run_id=baseline_run_id,
                candidate_run_id=candidate_run_id,
                metric_identifiers=["language/exact-match"],
                bootstrap_method="percentile",
                bootstrap_resamples=1_000,
                test="permutation",
                seed=20260730,
                missing_data_policy=MissingDataPolicy.AVAILABLE_PAIRS,
                practical_difference=0.05,
            )
            metric = compare_metric(
                metric_identifier="language/exact-match",
                metric_version="1.0.0",
                baseline=by_run[baseline_run_id],
                candidate=by_run[candidate_run_id],
                confidence=configuration.confidence,
                bootstrap_method=configuration.bootstrap_method,
                bootstrap_resamples=configuration.bootstrap_resamples,
                test=configuration.test,
                seed=configuration.seed,
                missing_data_policy=MissingDataPolicy(configuration.missing_data_policy),
                practical_difference=configuration.practical_difference,
                top_changed_examples=configuration.top_changed_examples,
            )
            comparison = ComparisonRead(
                id=new_uuid7(),
                project_id=DEMO_PROJECT_ID,
                baseline_run_id=baseline_run_id,
                candidate_run_id=candidate_run_id,
                baseline_dataset_version_id=version_id,
                candidate_dataset_version_id=version_id,
                dataset_compatible=True,
                intersection_only=False,
                configuration=configuration,
                metrics=[metric],
                limitations=[
                    "This synthetic three-record demonstration has very low statistical power.",
                    "The fake provider proves orchestration, not external model quality.",
                ],
            )
            session.add(
                ComparisonModel(
                    id=comparison.id,
                    organization_id=DEMO_ORGANIZATION_ID,
                    project_id=DEMO_PROJECT_ID,
                    baseline_run_id=baseline_run_id,
                    candidate_run_id=candidate_run_id,
                    baseline_dataset_version_id=version_id,
                    candidate_dataset_version_id=version_id,
                    configuration=configuration.model_dump(mode="json"),
                    results=[metric.model_dump(mode="json")],
                    limitations=comparison.limitations,
                )
            )
            await session.commit()

        report = comparison_markdown(comparison).encode()
        store = S3ObjectStore(
            endpoint_url=settings.s3_endpoint_url,
            region=settings.s3_region,
            bucket=settings.s3_bucket,
            access_key_id=settings.s3_access_key_id.get_secret_value(),
            secret_access_key=settings.s3_secret_access_key.get_secret_value(),
        )
        await store.ensure_bucket()
        object_key = f"reports/demo/{comparison.id}/comparison.md"
        stored = await store.put(object_key, report, media_type="text/markdown; charset=utf-8")
        async with factory() as session:
            session.add(
                ArtifactModel(
                    organization_id=DEMO_ORGANIZATION_ID,
                    project_id=DEMO_PROJECT_ID,
                    object_key=stored.key,
                    content_hash=stored.content_hash,
                    byte_size=stored.byte_size,
                    media_type=stored.media_type,
                    sensitivity="internal",
                    ready=True,
                )
            )
            await session.commit()
        gate = evaluate_gate(
            GateConfiguration.model_validate(
                {
                    "version": "1.0.0",
                    "rules": [
                        {
                            "identifier": "no-exact-match-regression",
                            "metric_identifier": "language/exact-match",
                            "operator": "maximum_regression",
                            "threshold": 0,
                            "minimum_paired_count": 3,
                        }
                    ],
                }
            ),
            comparison,
        )
        return {
            "baseline_experiment_id": str(baseline_experiment.id),
            "candidate_experiment_id": str(candidate_experiment.id),
            "baseline_run_id": str(baseline_run_id),
            "candidate_run_id": str(candidate_run_id),
            "baseline_state": baseline_run.state,
            "candidate_state": candidate_run.state,
            "sample_count": len(samples),
            "response_count": len(responses),
            "metric_result_count": len(metric_rows),
            "comparison_id": str(comparison.id),
            "paired_count": metric.paired_count,
            "exact_match_delta": metric.mean_difference,
            "confidence_interval": metric.confidence_interval.model_dump(mode="json"),
            "gate_passed": gate.passed,
            "report_object_key": stored.key,
            "report_sha256": stored.content_hash,
            "actual_cost_usd": "0.000000000000",
            "reproduce": (
                f"evalctl compare --project-id {DEMO_PROJECT_ID} "
                f"--baseline-run-id {baseline_run_id} "
                f"--candidate-run-id {candidate_run_id}"
            ),
        }
    finally:
        await engine.dispose()


def main() -> None:
    """Execute the local demonstration and print JSON."""

    print(json.dumps(asyncio.run(run_demo()), default=str, sort_keys=True))


if __name__ == "__main__":
    main()
