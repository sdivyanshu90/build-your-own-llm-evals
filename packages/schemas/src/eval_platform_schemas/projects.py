"""Project API schemas."""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import Field

from eval_platform_schemas.common import StrictModel


class ProjectCreate(StrictModel):
    """Create-project request."""

    slug: str = Field(min_length=1, max_length=63)
    name: str = Field(min_length=1, max_length=200)
    budget_amount: Decimal = Field(default=Decimal("100"), ge=0)
    concurrency_limit: int = Field(default=8, ge=1, le=10_000)


class ProjectRead(StrictModel):
    """Project response."""

    id: uuid.UUID
    organization_id: uuid.UUID
    slug: str
    name: str
    budget_amount: Decimal
    budget_currency: str
    concurrency_limit: int
    version_stamp: int
