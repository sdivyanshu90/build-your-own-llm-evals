"""Bounded judge execution, ensemble, drift, and cost-accounting tests."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

import pytest
from eval_platform_evaluators.diagnostics import ensemble_disagreement, judge_drift
from eval_platform_evaluators.execution import evaluate_with_judge
from eval_platform_evaluators.judge import (
    AggregationStrategy,
    JudgeConfiguration,
    JudgeMode,
    JudgeResponse,
    Rubric,
    RubricDimension,
)
from eval_platform_evaluators.pairwise import Verdict
from eval_platform_providers.base import (
    EmbeddingRequest,
    EmbeddingResponse,
    GenerationRequest,
    GenerationResponse,
    ProviderCapability,
    StructuredOutputRequest,
    Usage,
)


def _response(
    verdict: str,
    score: float,
    confidence: float = 0.8,
) -> dict[str, Any]:
    return {
        "schema_version": "judge-response/1",
        "verdict": verdict,
        "scores": {"quality": score},
        "confidence": confidence,
        "evidence": ["A:L0001"],
        "justification": "The cited answer meets the rubric.",
        "abstention_reason": None,
    }


class ScriptedProvider:
    """Minimal provider contract implementation returning a finite script."""

    def __init__(self, values: list[dict[str, Any]]) -> None:
        self.values = values
        self.calls = 0
        self.idempotency_keys: list[str | None] = []

    @property
    def identifier(self) -> str:
        return "scripted"

    def capabilities(self) -> frozenset[ProviderCapability]:
        return frozenset(ProviderCapability)

    async def generate_structured(
        self,
        request: StructuredOutputRequest,
    ) -> GenerationResponse:
        self.idempotency_keys.append(request.generation.idempotency_key)
        value = self.values[self.calls]
        self.calls += 1
        return GenerationResponse(
            text="",
            model=request.generation.model,
            finish_reason="stop",
            usage=Usage(3, 2, 5, actual_cost="0.01"),
            provider_request_id=f"call-{self.calls}",
            structured=value,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise RuntimeError(f"unexpected unstructured request for {request.model}")

    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        raise RuntimeError(f"unexpected embedding request for {request.model}")

    def count_tokens(self, model: str, text: str) -> int:
        return len(model) + len(text)


def _rubric() -> Rubric:
    return Rubric(
        identifier="quality",
        version="1.0.0",
        title="Quality",
        instructions="Rate only correctness.",
        dimensions=(
            RubricDimension(
                identifier="quality",
                description="Correctness and relevance.",
                minimum=1,
                maximum=5,
            ),
        ),
    )


def _configuration(
    *,
    repetitions: int = 1,
    aggregation: AggregationStrategy = AggregationStrategy.MAJORITY,
) -> JudgeConfiguration:
    return JudgeConfiguration(
        identifier="judge",
        version="1.0.0",
        provider="scripted",
        model="scripted-judge",
        mode=JudgeMode.POINTWISE,
        prompt_version="1",
        repetitions=repetitions,
        aggregation=aggregation,
        seed=9,
        data_handling_policy="Synthetic test data only.",
    )


@pytest.mark.asyncio
async def test_executor_repairs_once_and_accounts_for_all_billed_calls() -> None:
    invalid = _response("A", 5)
    invalid["scores"] = {}
    provider = ScriptedProvider([invalid, _response("A", 4)])
    delays: list[float] = []

    def sleeper(delay: float) -> Awaitable[None]:
        delays.append(delay)

        async def complete() -> None:
            return None

        return complete()

    evaluation = await evaluate_with_judge(
        provider=provider,
        configuration=_configuration(),
        rubric=_rubric(),
        candidate_a="A supported answer.",
        sleeper=sleeper,
    )

    assert evaluation.verdict is Verdict.A
    assert evaluation.scores == {"quality": 4}
    assert evaluation.total_usage.total_tokens == 10
    assert evaluation.total_usage.actual_cost == "0.02"
    assert provider.calls == 2
    assert provider.idempotency_keys[0] != provider.idempotency_keys[1]
    assert len(delays) == 1


@pytest.mark.asyncio
async def test_repetition_aggregation_reports_ties_abstentions_and_mean_scores() -> None:
    abstention = _response("abstain", 3, 0.2)
    abstention["abstention_reason"] = "Insufficient evidence."
    provider = ScriptedProvider([_response("A", 5, 0.9), _response("B", 3, 0.7), abstention])
    evaluation = await evaluate_with_judge(
        provider=provider,
        configuration=_configuration(
            repetitions=3,
            aggregation=AggregationStrategy.MEAN,
        ),
        rubric=_rubric(),
        candidate_a="Answer.",
    )
    assert evaluation.verdict is Verdict.TIE
    assert evaluation.abstentions == 1
    assert evaluation.disagreement_rate == 0.5
    assert evaluation.scores == {"quality": 4}
    assert evaluation.confidence == pytest.approx(0.8)


def test_drift_and_ensemble_disagreement_are_auditable() -> None:
    baseline = [JudgeResponse.model_validate(_response("A", 4)) for _ in range(4)]
    current = [JudgeResponse.model_validate(_response("B", 2)) for _ in range(4)]
    drift = judge_drift(baseline, current)
    assert drift.alert
    assert drift.verdict_total_variation == 1
    assert drift.mean_score_shifts == {"quality": -2}
    diagnostic = ensemble_disagreement({"judge-one": baseline, "judge-two": current})
    assert diagnostic["sample_count"] == 4
    assert diagnostic["disagreement_rate"] == 1
