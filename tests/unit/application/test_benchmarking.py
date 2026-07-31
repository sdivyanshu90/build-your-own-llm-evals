"""Behavior tests for reproducible remote-model benchmark aggregation."""

from __future__ import annotations

from pathlib import Path

import pytest
from eval_platform_application.benchmarking import (
    BenchmarkCase,
    BenchmarkObservation,
    aggregate_benchmark,
    benchmark_schedule,
    is_correct,
    load_benchmark_cases,
    normalize_benchmark_answer,
)


def _observation(
    case: BenchmarkCase,
    repetition: int,
    *,
    response: str | None,
    latency: float = 100,
) -> BenchmarkObservation:
    completed = response is not None
    return BenchmarkObservation(
        case_id=case.identifier,
        category=case.category,
        repetition=repetition,
        status="completed" if completed else "failed",
        response=response,
        normalized_response=normalize_benchmark_answer(response) if response else None,
        correct=is_correct(response, case.accepted_answers) if response else False,
        latency_ms=latency,
        input_tokens=10 if completed else 0,
        output_tokens=2 if completed else 0,
        attempts=1,
        error_kind=None if completed else "timeout",
    )


def test_benchmark_dataset_is_valid_and_hashed() -> None:
    cases, digest = load_benchmark_cases(Path("examples/benchmarks/core-v1.jsonl"))

    assert len(cases) == 24
    assert len({case.identifier for case in cases}) == 24
    assert len(digest) == 64


def test_answer_normalization_is_bounded() -> None:
    assert normalize_benchmark_answer("```text\n PARIS. \n```") == "paris"
    assert is_correct("Paris!", ("paris",))
    assert not is_correct("Paris, France", ("paris",))


def test_schedule_is_seeded_and_complete() -> None:
    cases = (
        BenchmarkCase("a", "one", "A", ("a",)),
        BenchmarkCase("b", "two", "B", ("b",)),
    )

    first = benchmark_schedule(cases, repetitions=3, seed=7)
    second = benchmark_schedule(cases, repetitions=3, seed=7)

    assert first == second
    assert sorted((case.identifier, repetition) for case, repetition in first) == [
        ("a", 0),
        ("a", 1),
        ("a", 2),
        ("b", 0),
        ("b", 1),
        ("b", 2),
    ]


def test_aggregation_uses_case_majority_and_keeps_failures() -> None:
    cases = (
        BenchmarkCase("a", "one", "A", ("yes",)),
        BenchmarkCase("b", "two", "B", ("no",)),
    )
    observations = [
        _observation(cases[0], 0, response="yes", latency=90),
        _observation(cases[0], 1, response="yes", latency=100),
        _observation(cases[0], 2, response=None, latency=110),
        _observation(cases[1], 0, response="yes", latency=120),
        _observation(cases[1], 1, response="no", latency=130),
        _observation(cases[1], 2, response="yes", latency=140),
    ]

    result = aggregate_benchmark(
        cases,
        observations,
        repetitions=3,
        confidence=0.95,
        bootstrap_resamples=1_000,
        seed=11,
        input_price_per_million=1.5,
        output_price_per_million=7.5,
    )

    assert result["primary"]["correct"] == 1
    assert result["primary"]["accuracy"] == 0.5
    assert result["request_level"]["correct"] == 3
    assert result["failures"]["count"] == 1
    assert result["failures"]["by_kind"] == {"timeout": 1}
    assert result["reliability"]["fully_consistent_cases"] == 0
    assert result["usage"]["total_tokens"] == 60


def test_aggregation_rejects_silent_denominator_loss() -> None:
    case = BenchmarkCase("a", "one", "A", ("yes",))

    with pytest.raises(ValueError, match="expected 3"):
        aggregate_benchmark(
            (case,),
            [_observation(case, 0, response="yes")],
            repetitions=3,
            confidence=0.95,
            bootstrap_resamples=1_000,
            seed=1,
            input_price_per_million=1.5,
            output_price_per_million=7.5,
        )
