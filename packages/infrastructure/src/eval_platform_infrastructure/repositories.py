"""SQLAlchemy repositories for application ports."""

from __future__ import annotations

import uuid

from eval_platform_application.projects import Project
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.money import Money
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eval_platform_infrastructure.models import ProjectModel


class SqlProjectRepository:
    """Tenant-scoped PostgreSQL project repository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, project: Project) -> None:
        """Stage a new project in the current transaction."""

        existing = await self._session.scalar(
            select(ProjectModel.id).where(
                ProjectModel.organization_id == project.organization_id,
                ProjectModel.slug == project.slug,
                ProjectModel.deleted_at.is_(None),
            )
        )
        if existing is not None:
            raise DomainError(ErrorCode.CONFLICT, "project slug already exists")
        self._session.add(
            ProjectModel(
                id=project.id,
                organization_id=project.organization_id,
                slug=project.slug,
                name=project.name,
                budget_amount=project.budget.amount,
                budget_currency=project.budget.currency,
                concurrency_limit=project.concurrency_limit,
                version_stamp=project.version_stamp,
            )
        )

    async def get(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Get a non-deleted project in the supplied organization."""

        model = await self._session.scalar(
            select(ProjectModel).where(
                ProjectModel.organization_id == organization_id,
                ProjectModel.id == project_id,
                ProjectModel.deleted_at.is_(None),
            )
        )
        return None if model is None else _to_project(model)

    async def list(
        self, organization_id: uuid.UUID, *, limit: int, after: uuid.UUID | None
    ) -> list[Project]:
        """List projects using UUID keyset pagination."""

        statement = (
            select(ProjectModel)
            .where(
                ProjectModel.organization_id == organization_id,
                ProjectModel.deleted_at.is_(None),
            )
            .order_by(ProjectModel.id)
            .limit(limit)
        )
        if after is not None:
            statement = statement.where(ProjectModel.id > after)
        models = (await self._session.scalars(statement)).all()
        return [_to_project(model) for model in models]


def _to_project(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        organization_id=model.organization_id,
        slug=model.slug,
        name=model.name,
        budget=Money(model.budget_amount, model.budget_currency),
        concurrency_limit=model.concurrency_limit,
        version_stamp=model.version_stamp,
    )
