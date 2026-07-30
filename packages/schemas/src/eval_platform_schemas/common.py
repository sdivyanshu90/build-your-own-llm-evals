"""Shared API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """Reject unknown external fields and serialize enums by value."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        populate_by_name=True,
    )


class ErrorDetail(StrictModel):
    """One structured field or domain error detail."""

    location: list[str | int] = Field(default_factory=list)
    message: str
    code: str


class ErrorResponse(StrictModel):
    """Stable v1 error envelope."""

    error: str
    message: str
    request_id: str
    details: list[ErrorDetail] = Field(default_factory=list)


class PageMetadata(StrictModel):
    """Keyset-pagination metadata."""

    next_cursor: str | None = None
    limit: int = Field(ge=1, le=200)


class Page[T](StrictModel):
    """A page of typed resources."""

    items: list[T]
    page: PageMetadata
