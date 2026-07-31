"""Project-scoped service-account credential management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from eval_platform_domain.auth import Action, ProjectRole, authorize, role_actions
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_infrastructure.audit import append_audit_event
from eval_platform_infrastructure.models import ApiKeyModel
from eval_platform_infrastructure.security import api_key_digest, generate_api_key
from eval_platform_schemas.access import (
    ServiceAccountCreate,
    ServiceAccountCreated,
    ServiceAccountRead,
)
from fastapi import APIRouter, Request, status
from sqlalchemy import select

from eval_platform_api.dependencies import (
    PrincipalDependency,
    SessionDependency,
    SettingsDependency,
)

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/service-accounts",
    tags=["access"],
)


@router.post("", response_model=ServiceAccountCreated, status_code=status.HTTP_201_CREATED)
async def create_service_account(
    project_id: uuid.UUID,
    body: ServiceAccountCreate,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
    settings: SettingsDependency,
) -> ServiceAccountCreated:
    """Create a project credential and reveal its raw value exactly once."""

    _admin(principal, project_id)
    try:
        scopes = [Action(scope) for scope in body.scopes]
    except ValueError as error:
        raise DomainError(
            ErrorCode.VALIDATION,
            "service-account scope is unknown",
        ) from error
    role_permissions = role_actions(ProjectRole(body.role))
    if any(scope not in role_permissions for scope in scopes):
        raise DomainError(
            ErrorCode.VALIDATION,
            "a service-account scope cannot exceed its role",
        )
    if body.expires_at is not None and body.expires_at <= datetime.now(UTC):
        raise DomainError(ErrorCode.VALIDATION, "expiration must be in the future")
    raw, prefix = generate_api_key()
    model = ApiKeyModel(
        organization_id=principal.organization_id,
        project_id=project_id,
        name=body.name.strip(),
        prefix=prefix,
        secret_digest=api_key_digest(
            raw,
            settings.api_key_pepper.get_secret_value(),
        ),
        role=body.role,
        scopes=[scope.value for scope in scopes],
        expires_at=body.expires_at,
    )
    session.add(model)
    await session.flush()
    await append_audit_event(
        session,
        organization_id=principal.organization_id,
        project_id=project_id,
        actor_subject=principal.subject,
        action="service_account.create",
        target_type="service_account",
        target_id=model.id,
        outcome="succeeded",
        request_id=request.state.request_id,
        summary={"name": model.name, "role": model.role, "scopes": model.scopes},
    )
    return ServiceAccountCreated(
        **_read(model).model_dump(mode="python"),
        api_key=raw,
    )


@router.get("", response_model=list[ServiceAccountRead])
async def list_service_accounts(
    project_id: uuid.UUID,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> list[ServiceAccountRead]:
    """List credential descriptors; raw keys and digests never leave storage."""

    _admin(principal, project_id)
    values = (
        await session.scalars(
            select(ApiKeyModel)
            .where(
                ApiKeyModel.organization_id == principal.organization_id,
                ApiKeyModel.project_id == project_id,
            )
            .order_by(ApiKeyModel.id)
        )
    ).all()
    return [_read(value) for value in values]


@router.post("/{service_account_id}/revoke", response_model=ServiceAccountRead)
async def revoke_service_account(
    project_id: uuid.UUID,
    service_account_id: uuid.UUID,
    request: Request,
    principal: PrincipalDependency,
    session: SessionDependency,
) -> ServiceAccountRead:
    """Idempotently revoke a service-account credential."""

    _admin(principal, project_id)
    model = await session.scalar(
        select(ApiKeyModel)
        .where(
            ApiKeyModel.organization_id == principal.organization_id,
            ApiKeyModel.project_id == project_id,
            ApiKeyModel.id == service_account_id,
        )
        .with_for_update()
    )
    if model is None:
        raise DomainError(ErrorCode.NOT_FOUND, "service account was not found")
    if model.revoked_at is None:
        model.revoked_at = datetime.now(UTC)
        await append_audit_event(
            session,
            organization_id=principal.organization_id,
            project_id=project_id,
            actor_subject=principal.subject,
            action="service_account.revoke",
            target_type="service_account",
            target_id=model.id,
            outcome="succeeded",
            request_id=request.state.request_id,
            summary={"prefix": model.prefix},
        )
    return _read(model)


def _read(model: ApiKeyModel) -> ServiceAccountRead:
    return ServiceAccountRead(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        prefix=model.prefix,
        role=model.role,
        scopes=model.scopes,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        last_used_at=model.last_used_at,
    )


def _admin(principal: PrincipalDependency, project_id: uuid.UUID) -> None:
    authorize(
        principal,
        Action.PROJECT_ADMIN,
        organization_id=principal.organization_id,
        project_id=project_id,
    )
