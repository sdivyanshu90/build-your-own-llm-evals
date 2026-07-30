"""Provider retry classification, limits, and deterministic timing tests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from eval_platform_application.retry import RetryPolicy, call_with_retry
from eval_platform_providers.base import ProviderError, ProviderErrorKind


@pytest.mark.asyncio
async def test_retryable_error_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    operation = AsyncMock(
        side_effect=[
            ProviderError(ProviderErrorKind.RATE_LIMIT, "limited", retry_after_seconds=0.01),
            "ok",
        ]
    )
    sleep = AsyncMock()
    monkeypatch.setattr("eval_platform_application.retry.asyncio.sleep", sleep)
    result = await call_with_retry(
        operation,
        RetryPolicy(max_attempts=3, timeout_seconds=1),
        seed=42,
    )
    assert result == "ok"
    assert operation.await_count == 2
    sleep.assert_awaited_once()


@pytest.mark.asyncio
async def test_terminal_error_is_not_retried() -> None:
    operation = AsyncMock(
        side_effect=ProviderError(ProviderErrorKind.AUTHENTICATION, "invalid credential")
    )
    with pytest.raises(ProviderError) as captured:
        await call_with_retry(
            operation,
            RetryPolicy(max_attempts=4, timeout_seconds=1),
            seed=0,
        )
    assert captured.value.kind is ProviderErrorKind.AUTHENTICATION
    assert operation.await_count == 1
