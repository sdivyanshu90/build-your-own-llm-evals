"""Project role-based access-control policy."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum

from eval_platform_domain.errors import DomainError, ErrorCode


class ProjectRole(StrEnum):
    """Stable project roles ordered by explicit permissions, not enum value."""

    ADMIN = "admin"
    EDITOR = "editor"
    RUNNER = "runner"
    VIEWER = "viewer"


class Action(StrEnum):
    """Actions understood by the initial authorization policy."""

    PROJECT_READ = "project:read"
    PROJECT_ADMIN = "project:admin"
    DATASET_READ = "dataset:read"
    DATASET_WRITE = "dataset:write"
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"
    RUN_READ = "run:read"
    RUN_START = "run:start"
    RUN_CANCEL = "run:cancel"
    JUDGMENT_WRITE = "judgment:write"
    ANALYSIS_WRITE = "analysis:write"
    REPORT_EXPORT = "report:export"
    AUDIT_READ = "audit:read"


_ROLE_ACTIONS: dict[ProjectRole, frozenset[Action]] = {
    ProjectRole.VIEWER: frozenset(
        {
            Action.PROJECT_READ,
            Action.DATASET_READ,
            Action.CONFIG_READ,
            Action.RUN_READ,
        }
    ),
    ProjectRole.RUNNER: frozenset(
        {
            Action.PROJECT_READ,
            Action.DATASET_READ,
            Action.CONFIG_READ,
            Action.RUN_READ,
            Action.RUN_START,
            Action.RUN_CANCEL,
            Action.JUDGMENT_WRITE,
            Action.ANALYSIS_WRITE,
            Action.REPORT_EXPORT,
        }
    ),
    ProjectRole.EDITOR: frozenset(
        {
            Action.PROJECT_READ,
            Action.DATASET_READ,
            Action.DATASET_WRITE,
            Action.CONFIG_READ,
            Action.CONFIG_WRITE,
            Action.RUN_READ,
            Action.RUN_START,
            Action.RUN_CANCEL,
            Action.JUDGMENT_WRITE,
            Action.ANALYSIS_WRITE,
            Action.REPORT_EXPORT,
        }
    ),
    ProjectRole.ADMIN: frozenset(Action),
}


def role_actions(role: ProjectRole) -> frozenset[Action]:
    """Return the immutable permission ceiling for a project role."""

    return _ROLE_ACTIONS[role]


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated actor with a tenant binding and optional API-key scopes."""

    subject: str
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    role: ProjectRole
    scopes: frozenset[Action] | None = None


def authorize(
    principal: Principal,
    action: Action,
    *,
    organization_id: uuid.UUID,
    project_id: uuid.UUID | None = None,
) -> None:
    """Raise a safe denial unless the principal may perform ``action``."""

    same_tenant = principal.organization_id == organization_id
    same_project = project_id is None or principal.project_id in {None, project_id}
    role_allows = action in _ROLE_ACTIONS[principal.role]
    scope_allows = principal.scopes is None or action in principal.scopes
    if not (same_tenant and same_project and role_allows and scope_allows):
        raise DomainError(ErrorCode.NOT_FOUND, "resource was not found")
