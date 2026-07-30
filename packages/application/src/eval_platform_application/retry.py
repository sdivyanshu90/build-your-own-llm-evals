"""Bounded provider execution with full-jitter retry and timeouts."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from eval_platform_providers.base import ProviderError, ProviderErrorKind


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Provider retry and timeout budget."""

    max_attempts: int = 4
    timeout_seconds: float = 60
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 30
    max_retry_after_seconds: float = 120

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        if (
            min(
                self.timeout_seconds,
                self.base_delay_seconds,
                self.max_delay_seconds,
                self.max_retry_after_seconds,
            )
            <= 0
        ):
            raise ValueError("retry durations must be positive")


async def call_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    *,
    seed: int,
    on_attempt: Callable[[int, ProviderError | None], Awaitable[None]] | None = None,
) -> T:
    """Call an operation under timeout and bounded full-jitter retry."""

    generator = random.Random(seed)  # noqa: S311 - reproducible jitter is intentional
    last_error: ProviderError | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            async with asyncio.timeout(policy.timeout_seconds):
                result = await operation()
            if on_attempt is not None:
                await on_attempt(attempt, None)
            return result
        except TimeoutError as error:
            last_error = ProviderError(
                kind=ProviderErrorKind.TIMEOUT,
                message="provider operation exceeded the platform timeout",
                ambiguous_billing=True,
            )
            last_error.__cause__ = error
        except ProviderError as error:
            last_error = error
        if on_attempt is not None:
            await on_attempt(attempt, last_error)
        if not last_error.retryable or attempt == policy.max_attempts:
            raise last_error
        exponential_cap = min(
            policy.max_delay_seconds,
            policy.base_delay_seconds * (2 ** (attempt - 1)),
        )
        delay = generator.uniform(0, exponential_cap)
        if last_error.retry_after_seconds is not None:
            delay = max(
                delay,
                min(last_error.retry_after_seconds, policy.max_retry_after_seconds),
            )
        await asyncio.sleep(delay)
    raise RuntimeError("retry loop exhausted without a result or provider error")
