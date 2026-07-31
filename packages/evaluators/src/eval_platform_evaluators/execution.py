"""Bounded, provider-neutral execution and aggregation of structured judge calls."""

from __future__ import annotations

import asyncio
import hashlib
import statistics
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal

from eval_platform_providers.base import (
    ChatMessage,
    GenerationRequest,
    Provider,
    ProviderError,
    StructuredOutputRequest,
    Usage,
)

from eval_platform_evaluators.judge import (
    AggregationStrategy,
    JudgeConfiguration,
    JudgeResponse,
    Rubric,
    build_judge_messages,
    evidence_ids,
    parse_judge_response,
)
from eval_platform_evaluators.pairwise import Verdict

Sleeper = Callable[[float], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class JudgeAttempt:
    """Sanitized provenance for one provider call."""

    repetition: int
    attempt: int
    provider_request_id: str | None
    usage: Usage
    response: JudgeResponse


@dataclass(frozen=True, slots=True)
class JudgeEvaluation:
    """Independent judgments and their transparent aggregate."""

    verdict: Verdict
    scores: dict[str, float]
    confidence: float
    disagreement_rate: float
    abstentions: int
    attempts: tuple[JudgeAttempt, ...]
    total_usage: Usage


async def evaluate_with_judge(
    *,
    provider: Provider,
    configuration: JudgeConfiguration,
    rubric: Rubric,
    candidate_a: str,
    candidate_b: str | None = None,
    reference: str | None = None,
    trusted_metadata: dict[str, str] | None = None,
    sleeper: Sleeper = asyncio.sleep,
) -> JudgeEvaluation:
    """Run configured independent judgments with bounded validation retries."""

    allowed_evidence = evidence_ids("A", candidate_a)
    if candidate_b is not None:
        allowed_evidence |= evidence_ids("B", candidate_b)
    if reference is not None:
        allowed_evidence |= evidence_ids("R", reference)
    attempts: list[JudgeAttempt] = []
    cost = Decimal("0")
    input_tokens = output_tokens = 0
    currencies: set[str] = set()
    estimated = False
    reported_cost = False
    for repetition in range(configuration.repetitions):
        response: JudgeResponse | None = None
        last_error: Exception | None = None
        repair_attempts = 0
        for attempt in range(1, configuration.max_attempts + 1):
            nonce = _nonce(configuration, repetition)
            messages = build_judge_messages(
                configuration=configuration,
                rubric=rubric,
                candidate_a=candidate_a,
                candidate_b=candidate_b,
                reference=reference,
                trusted_metadata=trusted_metadata,
                nonce=nonce,
            )
            if repair_attempts:
                messages = (
                    *messages,
                    {
                        "role": "user",
                        "content": (
                            "TRUSTED_REPAIR: the prior response failed strict validation. "
                            "Return exactly one judge-response/1 JSON object."
                        ),
                    },
                )
            request = StructuredOutputRequest(
                generation=GenerationRequest(
                    model=configuration.model,
                    messages=tuple(
                        ChatMessage(message["role"], message["content"]) for message in messages
                    ),
                    temperature=configuration.temperature,
                    max_output_tokens=1024,
                    seed=_repetition_seed(configuration, repetition),
                    idempotency_key=_idempotency_key(configuration, repetition, attempt),
                    metadata={
                        "judge_configuration": configuration.identifier,
                        "judge_version": configuration.version,
                        "rubric": rubric.identifier,
                        "rubric_version": rubric.version,
                    },
                ),
                schema=JudgeResponse.model_json_schema(),
                schema_name="judge_response_v1",
            )
            try:
                generated = await asyncio.wait_for(
                    provider.generate_structured(request),
                    timeout=configuration.timeout_seconds,
                )
                input_tokens += generated.usage.input_tokens
                output_tokens += generated.usage.output_tokens
                currencies.add(generated.usage.currency)
                estimated |= generated.usage.estimated
                if generated.usage.actual_cost is not None:
                    reported_cost = True
                    cost += Decimal(generated.usage.actual_cost)
                if cost > Decimal(str(configuration.cost_limit_usd)):
                    raise RuntimeError("judge cost limit exceeded")
                value = generated.structured if generated.structured is not None else generated.text
                response = parse_judge_response(
                    value,
                    rubric=rubric,
                    allowed_evidence=allowed_evidence,
                )
                attempts.append(
                    JudgeAttempt(
                        repetition,
                        attempt,
                        generated.provider_request_id,
                        generated.usage,
                        response,
                    )
                )
                break
            except ProviderError as error:
                last_error = error
                if not error.retryable or attempt >= configuration.max_attempts:
                    raise
                await sleeper(_retry_delay(configuration, repetition, attempt))
            except (TimeoutError, ValueError) as error:
                last_error = error
                if (
                    repair_attempts >= configuration.max_repairs
                    or attempt >= configuration.max_attempts
                ):
                    raise ValueError("judge response validation retries exhausted") from error
                repair_attempts += 1
                await sleeper(_retry_delay(configuration, repetition, attempt))
        if response is None:
            raise RuntimeError("judge repetition ended without a response") from last_error
    if len(currencies) != 1:
        raise ValueError("judge provider returned inconsistent currencies")
    aggregate = aggregate_judge_responses(configuration, attempts)
    return JudgeEvaluation(
        aggregate.verdict,
        aggregate.scores,
        aggregate.confidence,
        aggregate.disagreement_rate,
        aggregate.abstentions,
        aggregate.attempts,
        Usage(
            input_tokens,
            output_tokens,
            input_tokens + output_tokens,
            actual_cost=str(cost) if reported_cost else None,
            currency=currencies.pop(),
            estimated=estimated,
        ),
    )


def aggregate_judge_responses(
    configuration: JudgeConfiguration,
    attempts: list[JudgeAttempt],
) -> JudgeEvaluation:
    """Aggregate completed repetitions while retaining abstentions and disagreement."""

    if len(attempts) != configuration.repetitions:
        raise ValueError("exactly one successful attempt is required per repetition")
    responses = [attempt.response for attempt in attempts]
    usable = [response for response in responses if response.verdict is not Verdict.ABSTAIN]
    verdict_counts = Counter(response.verdict for response in usable)
    abstentions = len(responses) - len(usable)
    if usable:
        maximum = max(verdict_counts.values())
        leaders = [verdict for verdict, count in verdict_counts.items() if count == maximum]
        verdict = leaders[0] if len(leaders) == 1 else Verdict.TIE
        disagreement = 1 - maximum / len(usable)
    else:
        verdict = Verdict.ABSTAIN
        disagreement = 1.0
    scores: dict[str, float] = {}
    for dimension in rubric_dimensions(attempts):
        values = [response.scores[dimension] for response in usable if dimension in response.scores]
        if not values:
            continue
        if configuration.aggregation is AggregationStrategy.MEAN:
            scores[dimension] = statistics.fmean(values)
        else:
            scores[dimension] = float(statistics.median(values))
    confidences = [response.confidence for response in usable]
    input_tokens = sum(attempt.usage.input_tokens for attempt in attempts)
    output_tokens = sum(attempt.usage.output_tokens for attempt in attempts)
    actual_costs = [
        Decimal(attempt.usage.actual_cost)
        for attempt in attempts
        if attempt.usage.actual_cost is not None
    ]
    currencies = {attempt.usage.currency for attempt in attempts}
    if len(currencies) != 1:
        raise ValueError("judge attempts have inconsistent currencies")
    return JudgeEvaluation(
        verdict=verdict,
        scores=scores,
        confidence=statistics.fmean(confidences) if confidences else 0.0,
        disagreement_rate=disagreement,
        abstentions=abstentions,
        attempts=tuple(attempts),
        total_usage=Usage(
            input_tokens,
            output_tokens,
            input_tokens + output_tokens,
            actual_cost=str(sum(actual_costs)) if actual_costs else None,
            currency=currencies.pop(),
            estimated=any(attempt.usage.estimated for attempt in attempts),
        ),
    )


def rubric_dimensions(attempts: list[JudgeAttempt]) -> tuple[str, ...]:
    """Return the common dimension set or reject inconsistent successful responses."""

    dimensions = {tuple(sorted(attempt.response.scores)) for attempt in attempts}
    if len(dimensions) != 1:
        raise ValueError("successful judge responses have inconsistent dimensions")
    return next(iter(dimensions))


def _nonce(configuration: JudgeConfiguration, repetition: int) -> str:
    source = f"{configuration.identifier}|{configuration.version}|{configuration.seed}|{repetition}"
    return hashlib.sha256(source.encode()).hexdigest()[:32]


def _repetition_seed(configuration: JudgeConfiguration, repetition: int) -> int | None:
    if configuration.seed is None:
        return None
    return (configuration.seed + repetition) % (1 << 63)


def _idempotency_key(
    configuration: JudgeConfiguration,
    repetition: int,
    attempt: int,
) -> str:
    source = (
        f"{configuration.identifier}|{configuration.version}|"
        f"{configuration.seed}|{repetition}|{attempt}"
    )
    return f"judge-{hashlib.sha256(source.encode()).hexdigest()[:32]}"


def _retry_delay(
    configuration: JudgeConfiguration,
    repetition: int,
    attempt: int,
) -> float:
    jitter_source = hashlib.sha256(f"{configuration.seed}|{repetition}|{attempt}".encode()).digest()
    jitter = int.from_bytes(jitter_source[:2], "big") / 65535
    return float(min(configuration.timeout_seconds / 2, (2 ** (attempt - 1)) + jitter))
