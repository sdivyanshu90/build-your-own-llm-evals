"""Project application service."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from eval_platform_domain.auth import Action, Principal, authorize
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_domain.ids import new_uuid7
from eval_platform_domain.money import Money

_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


@dataclass(frozen=True, slots=True)
class Project:
    """Application projection of a project."""

    id: uuid.UUID
    organization_id: uuid.UUID
    slug: str
    name: str
    budget: Money
    concurrency_limit: int
    version_stamp: int


class ProjectRepository(Protocol):
    """Persistence operations required by ``ProjectService``."""

    async def add(self, project: Project) -> None:
        """Stage a project for persistence."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def get(self, organization_id: uuid.UUID, project_id: uuid.UUID) -> Project | None:
        """Return a tenant-scoped project when present."""

        raise TypeError("protocol declaration has no runtime implementation")

    async def list(
        self, organization_id: uuid.UUID, *, limit: int, after: uuid.UUID | None
    ) -> list[Project]:
        """Return a keyset-ordered project page."""

        raise TypeError("protocol declaration has no runtime implementation")


class ProjectService:
    """Validate and orchestrate project operations."""

    def __init__(self, repository: ProjectRepository) -> None:
        self._repository = repository

    async def create(
        self,
        principal: Principal,
        *,
        slug: str,
        name: str,
        budget_amount: Decimal,
        concurrency_limit: int,
    ) -> Project:
        """Create a project in the principal's organization."""

        authorize(
            principal,
            Action.PROJECT_ADMIN,
            organization_id=principal.organization_id,
        )
        normalized_slug = slug.strip().lower()
        if not _SLUG.fullmatch(normalized_slug):
            raise DomainError(
                ErrorCode.VALIDATION,
                "slug must contain lowercase letters, digits, and internal hyphens",
            )
        clean_name = name.strip()
        if not clean_name:
            raise DomainError(ErrorCode.VALIDATION, "project name is required")
        if not 1 <= concurrency_limit <= 10_000:
            raise DomainError(
                ErrorCode.VALIDATION,
                "concurrency limit must be between 1 and 10000",
            )
        project = Project(
            id=new_uuid7(),
            organization_id=principal.organization_id,
            slug=normalized_slug,
            name=clean_name,
            budget=Money(budget_amount),
            concurrency_limit=concurrency_limit,
            version_stamp=1,
        )
        await self._repository.add(project)
        return project
