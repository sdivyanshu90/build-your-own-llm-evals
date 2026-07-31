"""Request-scoped database and identity dependencies."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, cast

from eval_platform_domain.auth import Action, Principal, ProjectRole
from eval_platform_infrastructure.models import ApiKeyModel
from eval_platform_infrastructure.security import api_key_digest
from eval_platform_infrastructure.settings import AuthMode, Settings
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def get_settings(request: Request) -> Settings:
    """Return application settings from the composition root."""

    return cast(Settings, request.app.state.settings)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a transaction-owned async session."""

    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def get_principal(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
    x_organization_id: Annotated[uuid.UUID | None, Header()] = None,
    x_project_id: Annotated[uuid.UUID | None, Header()] = None,
    x_role: Annotated[ProjectRole, Header()] = ProjectRole.ADMIN,
) -> Principal:
    """Authenticate a development header identity or scoped API key."""

    if settings.auth_mode is AuthMode.DEVELOPMENT:
        if x_organization_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="X-Organization-ID is required in development mode",
            )
        return Principal(
            subject="development-user",
            organization_id=x_organization_id,
            project_id=x_project_id,
            role=x_role,
        )

    if authorization is None or not authorization.startswith("Bearer evp_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    raw_key = authorization.removeprefix("Bearer ").strip()
    prefix = raw_key[:16]
    key = await session.scalar(select(ApiKeyModel).where(ApiKeyModel.prefix == prefix))
    now = datetime.now(UTC)
    if (
        key is None
        or key.revoked_at is not None
        or (key.expires_at is not None and key.expires_at <= now)
        or not hmac.compare_digest(
            api_key_digest(raw_key, settings.api_key_pepper.get_secret_value()),
            key.secret_digest,
        )
    ):
        hashlib.sha256(raw_key.encode()).digest()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")
    key.last_used_at = now
    scopes = frozenset(Action(scope) for scope in key.scopes)
    return Principal(
        subject=f"api-key:{key.id}",
        organization_id=key.organization_id,
        project_id=key.project_id,
        role=ProjectRole(key.role),
        scopes=scopes,
    )


SessionDependency = Annotated[AsyncSession, Depends(get_session)]
PrincipalDependency = Annotated[Principal, Depends(get_principal)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
