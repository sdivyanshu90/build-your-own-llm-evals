"""Idempotently seed a local organization, project, and demonstration dataset."""

from __future__ import annotations

import asyncio
import json
import uuid

from eval_platform_application.datasets import DatasetService
from eval_platform_domain.auth import Principal, ProjectRole
from eval_platform_domain.dataset_schemas import get_builtin_schema
from eval_platform_infrastructure.database import create_engine, create_session_factory
from eval_platform_infrastructure.dataset_models import DatasetModel, DatasetVersionModel
from eval_platform_infrastructure.dataset_repository import SqlDatasetRepository
from eval_platform_infrastructure.models import OrganizationModel, ProjectModel
from eval_platform_infrastructure.settings import Settings
from sqlalchemy import select

DEMO_ORGANIZATION_ID = uuid.UUID("01900000-0000-7000-8000-000000000001")
DEMO_PROJECT_ID = uuid.UUID("01900000-0000-7000-8000-000000000002")


async def seed() -> dict[str, str]:
    """Return stable IDs for a repeatable local QA dataset."""

    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            organization = await session.get(OrganizationModel, DEMO_ORGANIZATION_ID)
            if organization is None:
                session.add(
                    OrganizationModel(
                        id=DEMO_ORGANIZATION_ID,
                        slug="demo",
                        name="LLM Evaluation Demo",
                    )
                )
            project = await session.get(ProjectModel, DEMO_PROJECT_ID)
            if project is None:
                session.add(
                    ProjectModel(
                        id=DEMO_PROJECT_ID,
                        organization_id=DEMO_ORGANIZATION_ID,
                        slug="evaluation-demo",
                        name="Evaluation Demo",
                        concurrency_limit=settings.default_project_concurrency,
                        budget_amount=settings.default_budget_usd,
                        budget_currency="USD",
                    )
                )
            await session.flush()

            dataset_model = await session.scalar(
                select(DatasetModel).where(
                    DatasetModel.project_id == DEMO_PROJECT_ID,
                    DatasetModel.slug == "synthetic-qa",
                )
            )
            principal = Principal(
                subject="local-seed",
                organization_id=DEMO_ORGANIZATION_ID,
                project_id=DEMO_PROJECT_ID,
                role=ProjectRole.ADMIN,
            )
            repository = SqlDatasetRepository(session)
            service = DatasetService(repository)
            if dataset_model is None:
                dataset = await service.create_dataset(
                    principal,
                    project_id=DEMO_PROJECT_ID,
                    slug="synthetic-qa",
                    name="Synthetic QA",
                    description="Small, permissively licensed deterministic demonstration data.",
                    tags=("demo", "synthetic", "qa"),
                )
                await session.flush()
                publication = await service.publish_version(
                    principal,
                    project_id=DEMO_PROJECT_ID,
                    dataset_id=dataset.id,
                    schema_name="qa",
                    schema_version="1",
                    schema=get_builtin_schema("qa/v1"),
                    source_kind="synthetic-demo",
                    source_records=(
                        {
                            "key": "capital-france",
                            "payload": {
                                "question": "What is the capital of France?",
                                "context": None,
                                "answers": ["Paris"],
                            },
                            "metadata": {"difficulty": "easy", "language": "en"},
                            "splits": ["test"],
                        },
                        {
                            "key": "two-plus-two",
                            "payload": {
                                "question": "What is two plus two?",
                                "context": None,
                                "answers": ["4"],
                            },
                            "metadata": {"difficulty": "easy", "language": "en"},
                            "splits": ["test"],
                        },
                        {
                            "key": "water-formula",
                            "payload": {
                                "question": "What is the chemical formula for water?",
                                "context": None,
                                "answers": ["H2O"],
                            },
                            "metadata": {"difficulty": "easy", "language": "en"},
                            "splits": ["challenge"],
                        },
                    ),
                )
                version_id = publication.version.id
                dataset_id = dataset.id
            else:
                dataset_id = dataset_model.id
                found_version_id = await session.scalar(
                    select(DatasetVersionModel.id)
                    .where(DatasetVersionModel.dataset_id == dataset_model.id)
                    .order_by(DatasetVersionModel.version_number.desc())
                    .limit(1)
                )
                if found_version_id is None:
                    raise RuntimeError("seed dataset exists without a version")
                version_id = found_version_id
            await session.commit()
            return {
                "organization_id": str(DEMO_ORGANIZATION_ID),
                "project_id": str(DEMO_PROJECT_ID),
                "dataset_id": str(dataset_id),
                "dataset_version_id": str(version_id),
            }
    finally:
        await engine.dispose()


def main() -> None:
    """Seed local data and print machine-readable identifiers."""

    print(json.dumps(asyncio.run(seed()), sort_keys=True))


if __name__ == "__main__":
    main()
