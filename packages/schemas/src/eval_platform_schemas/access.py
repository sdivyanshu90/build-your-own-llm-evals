"""Service-account credential schemas."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field, field_validator

from eval_platform_schemas.common import StrictModel


class ServiceAccountCreate(StrictModel):
    """Create a project-scoped API key shown once."""

    name: str = Field(min_length=1, max_length=200)
    role: str = Field(pattern="^(admin|editor|runner|viewer)$")
    scopes: list[str] = Field(default_factory=list, max_length=100)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def name_is_not_blank(cls, value: str) -> str:
        """Reject credentials whose display name disappears after trimming."""

        stripped = value.strip()
        if not stripped:
            raise ValueError("name must contain a visible character")
        return stripped

    @field_validator("scopes")
    @classmethod
    def scopes_are_unique(cls, value: list[str]) -> list[str]:
        """Prevent ambiguous duplicate scope entries."""

        if len(value) != len(set(value)):
            raise ValueError("scopes must be unique")
        return value

    @field_validator("expires_at")
    @classmethod
    def expiration_is_timezone_aware(cls, value: datetime | None) -> datetime | None:
        """Normalize credential expiry to UTC and reject ambiguous timestamps."""

        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value.astimezone(UTC)


class ServiceAccountRead(StrictModel):
    """Credential descriptor without secret material."""

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    prefix: str
    role: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    last_used_at: datetime | None


class ServiceAccountCreated(ServiceAccountRead):
    """One-time raw API key response."""

    api_key: str
