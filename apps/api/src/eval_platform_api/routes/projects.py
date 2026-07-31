"""Project REST resources."""

from __future__ import annotations

import uuid

from eval_platform_application.projects import Project, ProjectService
from eval_platform_infrastructure.repositories import SqlProjectRepository
from eval_platform_schemas.common import Page, PageMetadata
from eval_platform_schemas.projects import ProjectCreate, ProjectRead
from fastapi import APIRouter, Query, status

from eval_platform_api.dependencies import PrincipalDependency, SessionDependency

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _read(project: Project) -> ProjectRead:
    return ProjectRead(
        id=project.id,
        organization_id=project.organization_id,
        slug=project.slug,
        name=project.name,
        budget_amount=project.budget.amount,
        budget_currency=project.budget.currency,
        concurrency_limit=project.concurrency_limit,
        version_stamp=project.version_stamp,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreate,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> ProjectRead:
    """Create a tenant-scoped project."""

    service = ProjectService(SqlProjectRepository(session))
    project = await service.create(
        principal,
        slug=body.slug,
        name=body.name,
        budget_amount=body.budget_amount,
        concurrency_limit=body.concurrency_limit,
    )
    return _read(project)


@router.get("", response_model=Page[ProjectRead])
async def list_projects(
    principal: PrincipalDependency,
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    after: uuid.UUID | None = None,
) -> Page[ProjectRead]:
    """List projects visible in the authenticated organization."""

    repository = SqlProjectRepository(session)
    projects = await repository.list(
        principal.organization_id,
        limit=limit + 1,
        after=after,
    )
    has_more = len(projects) > limit
    page = projects[:limit]
    return Page(
        items=[_read(project) for project in page],
        page=PageMetadata(
            next_cursor=str(page[-1].id) if has_more and page else None,
            limit=limit,
        ),
    )
