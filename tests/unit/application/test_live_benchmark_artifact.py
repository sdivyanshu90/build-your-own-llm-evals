"""Integrity checks for the published live benchmark evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eval_platform_application.benchmarking import (
    BenchmarkObservation,
    aggregate_benchmark,
    load_benchmark_cases,
)

RESULT_PATH = Path("benchmark-results/gemini-3.6-flash-2026-07-30.json")
DATASET_PATH = Path("examples/benchmarks/core-v1.jsonl")


def test_published_benchmark_recomputes_and_is_documented() -> None:
    report = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    cases, dataset_hash = load_benchmark_cases(DATASET_PATH)
    observations = tuple(
        BenchmarkObservation(**observation) for observation in report["observations"]
    )
    expected = aggregate_benchmark(
        cases,
        observations,
        repetitions=report["benchmark"]["repetitions"],
        confidence=0.95,
        bootstrap_resamples=10_000,
        seed=report["benchmark"]["schedule_seed"],
        input_price_per_million=report["results"]["usage"]["input_price_per_million_usd"],
        output_price_per_million=report["results"]["usage"]["output_price_per_million_usd"],
    )

    assert report["benchmark"]["dataset_sha256"] == dataset_hash
    assert report["results"] == expected
    assert len(observations) == report["benchmark"]["planned_requests"] == 72

    readme = Path("README.md").read_text(encoding="utf-8")
    result_hash = hashlib.sha256(RESULT_PATH.read_bytes()).hexdigest()
    assert dataset_hash in readme
    assert result_hash in readme


def test_published_benchmark_contains_no_api_credentials() -> None:
    serialized = RESULT_PATH.read_text(encoding="utf-8")

    assert "GEMINI_API_KEY" not in serialized
    assert "AIza" not in serialized
