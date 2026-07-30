"""Stable domain error taxonomy used across delivery mechanisms."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Machine-stable error codes."""

    VALIDATION = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    FORBIDDEN = "forbidden"
    UNAUTHENTICATED = "unauthenticated"
    IMMUTABLE = "immutable_resource"
    BUDGET_EXCEEDED = "budget_exceeded"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    PROVIDER = "provider_error"
    METRIC = "metric_error"
    INFRASTRUCTURE = "infrastructure_error"


class DomainError(Exception):
    """Expected, safe-to-present domain failure."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
