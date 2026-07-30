"""Application-service tests using explicit in-memory persistence ports."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import pytest
from eval_platform_application.datasets import DatasetService, VersionPublication
from eval_platform_application.experiments import (
    Experiment,
    ExperimentService,
    RunCreation,
)
from eval_platform_application.projects import Project, ProjectService
from eval_platform_domain.auth import Principal, ProjectRole
from eval_platform_domain.dataset_schemas import get_builtin_schema
from eval_platform_domain.datasets import Dataset, DatasetVersion
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.money import Money


class MemoryProjectRepository:
    def __init__(self) -> None:
        self.values: dict[uuid.UUID, Project] = {}

    async def add(self, project: Project) -> None:
        self.values[project.id] = project

    async def get(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        value = self.values.get(project_id)
        return value if value and value.organization_id == organization_id else None

    async def list(
        self,
        organization_id: uuid.UUID,
        *,
        limit: int,
        after: uuid.UUID | None,
    ) -> list[Project]:
        return [
            value
            for value in sorted(self.values.values(), key=lambda item: item.id)
            if value.organization_id == organization_id and (after is None or value.id > after)
        ][:limit]


class MemoryDatasetRepository:
    def __init__(self) -> None:
        self.datasets: dict[uuid.UUID, Dataset] = {}
        self.versions: dict[uuid.UUID, DatasetVersion] = {}

    async def add_dataset(self, dataset: Dataset) -> None:
        self.datasets[dataset.id] = dataset

    async def get_dataset(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        dataset_id: uuid.UUID,
    ) -> Dataset | None:
        value = self.datasets.get(dataset_id)
        return (
            value
            if value and value.organization_id == organization_id and value.project_id == project_id
            else None
        )

    async def list_datasets(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        *,
        limit: int,
        after: uuid.UUID | None,
    ) -> list[Dataset]:
        return [
            value
            for value in sorted(self.datasets.values(), key=lambda item: item.id)
            if value.organization_id == organization_id
            and value.project_id == project_id
            and (after is None or value.id > after)
        ][:limit]

    async def next_version_number(self, dataset_id: uuid.UUID) -> int:
        return (
            max(
                (
                    value.version_number
                    for value in self.versions.values()
                    if value.dataset_id == dataset_id
                ),
                default=0,
            )
            + 1
        )

    async def add_version(self, publication: VersionPublication) -> None:
        self.versions[publication.version.id] = publication.version

    async def get_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        value = self.versions.get(version_id)
        return (
            value
            if value and value.organization_id == organization_id and value.project_id == project_id
            else None
        )


class MemoryExperimentRepository:
    def __init__(self, version: DatasetVersion) -> None:
        self.version = version
        self.experiments: list[Experiment] = []
        self.runs: list[RunCreation] = []

    async def get_dataset_version(
        self,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
        version_id: uuid.UUID,
    ) -> DatasetVersion | None:
        if (
            self.version.id == version_id
            and self.version.organization_id == organization_id
            and self.version.project_id == project_id
        ):
            return self.version
        return None

    async def add_experiment(self, experiment: Experiment) -> None:
        self.experiments.append(experiment)

    async def add_run(self, creation: RunCreation) -> None:
        self.runs.append(creation)


@pytest.fixture
def identity() -> tuple[uuid.UUID, uuid.UUID, Principal]:
    organization_id = uuid.uuid4()
    project_id = uuid.uuid4()
    return (
        organization_id,
        project_id,
        Principal(
            subject="test",
            organization_id=organization_id,
            project_id=project_id,
            role=ProjectRole.ADMIN,
        ),
    )


async def test_project_service_normalizes_and_rejects_invalid_values(
    identity: tuple[uuid.UUID, uuid.UUID, Principal],
) -> None:
    organization_id, _, principal = identity
    repository = MemoryProjectRepository()
    project = await ProjectService(repository).create(
        principal,
        slug="  My-Project ",
        name=" Evaluation ",
        budget_amount=Decimal("12.50"),
        concurrency_limit=4,
    )
    assert project.organization_id == organization_id
    assert project.slug == "my-project"
    assert project.name == "Evaluation"
    assert project.budget == Money(Decimal("12.50"))
    assert await repository.get(organization_id, project.id) == project
    assert await repository.list(organization_id, limit=10, after=None) == [project]

    for values in (
        {"slug": "bad_slug", "name": "name", "concurrency_limit": 1},
        {"slug": "good", "name": " ", "concurrency_limit": 1},
        {"slug": "good", "name": "name", "concurrency_limit": 0},
    ):
        with pytest.raises(DomainError) as captured:
            await ProjectService(repository).create(
                principal,
                budget_amount=Decimal("1"),
                **values,
            )
        assert captured.value.code is ErrorCode.VALIDATION


async def test_dataset_publish_diff_and_validation(
    identity: tuple[uuid.UUID, uuid.UUID, Principal],
) -> None:
    organization_id, project_id, principal = identity
    repository = MemoryDatasetRepository()
    service = DatasetService(repository)
    dataset = await service.create_dataset(
        principal,
        project_id=project_id,
        slug="  QA-Data ",
        name=" QA ",
        tags=("English", "english", " test "),
    )
    assert dataset.organization_id == organization_id
    assert dataset.tags == ("english", "test")
    schema = get_builtin_schema("qa/v1")
    first = await service.publish_version(
        principal,
        project_id=project_id,
        dataset_id=dataset.id,
        schema_name="qa",
        schema_version="1",
        schema=schema,
        source_records=(
            {
                "key": "one",
                "payload": {"question": "One?", "context": None, "answers": ["1"]},
                "metadata": {"language": "en"},
                "splits": ["test"],
            },
            {
                "key": "duplicate-content",
                "payload": {"question": "One?", "context": None, "answers": ["1"]},
                "metadata": {},
                "splits": ["challenge"],
            },
        ),
    )
    assert first.validation.record_count == 2
    assert first.validation.duplicate_payload_count == 1
    assert first.validation.split_counts == {"challenge": 1, "test": 1}
    second = await service.publish_version(
        principal,
        project_id=project_id,
        dataset_id=dataset.id,
        schema_name="qa",
        schema_version="1",
        schema=schema,
        parent_version_ids=(first.version.id,),
        source_records=(
            {
                "key": "one",
                "payload": {"question": "One?", "context": None, "answers": ["one"]},
                "metadata": {"language": "en"},
                "splits": ["test"],
            },
            {
                "key": "new",
                "payload": {"question": "Two?", "context": None, "answers": ["2"]},
                "metadata": {},
                "splits": ["test"],
            },
        ),
    )
    assert second.version.version_number == 2
    result = await service.diff(
        principal,
        project_id=project_id,
        source_version_id=first.version.id,
        target_version_id=second.version.id,
    )
    assert {item.kind for item in result.records} == {"added", "removed", "modified"}

    invalid_rows: list[tuple[dict[str, Any], ...]] = [
        (),
        (
            {"key": "same", "payload": {}, "metadata": {}, "splits": []},
            {"key": "same", "payload": {}, "metadata": {}, "splits": []},
        ),
        ({"key": "x", "payload": "not-an-object", "metadata": {}, "splits": []},),
    ]
    for rows in invalid_rows:
        with pytest.raises(DomainError):
            await service.publish_version(
                principal,
                project_id=project_id,
                dataset_id=dataset.id,
                schema_name="qa",
                schema_version="1",
                schema=schema,
                source_records=rows,
            )


async def test_experiment_snapshot_run_seeds_budget_and_secret_rejection(
    identity: tuple[uuid.UUID, uuid.UUID, Principal],
) -> None:
    _, project_id, principal = identity
    dataset_repository = MemoryDatasetRepository()
    dataset_service = DatasetService(dataset_repository)
    dataset = await dataset_service.create_dataset(
        principal,
        project_id=project_id,
        slug="runs",
        name="Runs",
    )
    publication = await dataset_service.publish_version(
        principal,
        project_id=project_id,
        dataset_id=dataset.id,
        schema_name="generation",
        schema_version="1",
        schema=get_builtin_schema("generation/v1"),
        source_records=(
            {
                "key": "a",
                "payload": {"input": "A", "reference": "A"},
                "metadata": {},
                "splits": ["test"],
            },
            {
                "key": "b",
                "payload": {"input": "B", "reference": "B"},
                "metadata": {},
                "splits": ["test"],
            },
        ),
    )
    repository = MemoryExperimentRepository(publication.version)
    service = ExperimentService(repository)
    experiment = await service.create_experiment(
        principal,
        project_id=project_id,
        dataset_version_id=publication.version.id,
        provider={"type": "fake", "identifier": "fake/test"},
        model="fake-v1",
        prompt_template="Answer {{ input }}",
        parameters={"temperature": 0},
        suite={"task_type": "generation", "metrics": []},
        seed=42,
        application_version="test",
        dependency_lock_hash="lock",
    )
    assert repository.experiments == [experiment]
    assert "api_key" not in experiment.system_snapshot.provider
    creation = await service.create_run(
        principal,
        experiment=experiment,
        dataset_version=publication.version,
        repetitions=2,
        budget_limit=Money(Decimal("2")),
    )
    assert len(creation.tasks) == 4
    assert len({task.seed for task in creation.tasks}) == 4
    assert creation.run.state == "queued"
    assert repository.runs == [creation]

    with pytest.raises(DomainError, match="deployment secrets"):
        await service.create_experiment(
            principal,
            project_id=project_id,
            dataset_version_id=publication.version.id,
            provider={"api_key": "secret"},
            model="x",
            prompt_template="{{ input }}",
            parameters={},
            suite={},
            seed=0,
            application_version="test",
            dependency_lock_hash="lock",
        )
    with pytest.raises(DomainError, match="unsigned 64-bit"):
        await service.create_experiment(
            principal,
            project_id=project_id,
            dataset_version_id=publication.version.id,
            provider={"type": "fake"},
            model="x",
            prompt_template="{{ input }}",
            parameters={},
            suite={},
            seed=-1,
            application_version="test",
            dependency_lock_hash="lock",
        )
    with pytest.raises(DomainError, match="repetitions"):
        await service.create_run(
            principal,
            experiment=experiment,
            dataset_version=publication.version,
            repetitions=0,
            budget_limit=Money(Decimal("1")),
        )
