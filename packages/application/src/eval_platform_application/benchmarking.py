"""Reproducible aggregation for bounded remote-model benchmarks."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from eval_platform_statistics.intervals import proportion_interval


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One immutable exact-answer benchmark case."""

    identifier: str
    category: str
    prompt: str
    accepted_answers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkObservation:
    """One logical request, including failures in the planned denominator."""

    case_id: str
    category: str
    repetition: int
    status: str
    response: str | None
    normalized_response: str | None
    correct: bool
    latency_ms: float | None
    input_tokens: int
    output_tokens: int
    attempts: int
    provider_request_id: str | None = None
    error_kind: str | None = None


def normalize_benchmark_answer(value: str) -> str:
    """Normalize presentation-only variation without changing answer semantics."""

    normalized = unicodedata.normalize("NFC", value).strip()
    if normalized.startswith("```") and normalized.endswith("```"):
        normalized = re.sub(r"^```(?:text)?\s*", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s*```$", "", normalized)
    normalized = " ".join(normalized.split()).casefold()
    return normalized[:-1] if normalized.endswith((".", "!", "?")) else normalized


def load_benchmark_cases(path: Path) -> tuple[tuple[BenchmarkCase, ...], str]:
    """Load and validate JSONL cases and return their exact content hash."""

    content = path.read_bytes()
    cases: list[BenchmarkCase] = []
    seen: set[str] = set()
    for line_number, raw_line in enumerate(content.decode("utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        identifier = str(value["id"]).strip()
        category = str(value["category"]).strip()
        prompt = str(value["prompt"]).strip()
        answers = tuple(str(answer).strip() for answer in value["accepted_answers"])
        if not identifier or identifier in seen:
            raise ValueError(f"line {line_number} has an empty or duplicate id")
        if not category or not prompt or not answers or any(not answer for answer in answers):
            raise ValueError(f"line {line_number} has an empty required field")
        seen.add(identifier)
        cases.append(BenchmarkCase(identifier, category, prompt, answers))
    if len(cases) < 2:
        raise ValueError("a benchmark requires at least two cases")
    return tuple(cases), hashlib.sha256(content).hexdigest()


def is_correct(response: str, accepted_answers: Sequence[str]) -> bool:
    """Return whether a response equals any accepted answer after documented normalization."""

    normalized = normalize_benchmark_answer(response)
    return normalized in {normalize_benchmark_answer(answer) for answer in accepted_answers}


def benchmark_schedule(
    cases: Sequence[BenchmarkCase],
    *,
    repetitions: int,
    seed: int,
) -> tuple[tuple[BenchmarkCase, int], ...]:
    """Return a seeded interleaving that mitigates time and category ordering effects."""

    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    schedule = [(case, repetition) for repetition in range(repetitions) for case in cases]
    random.Random(seed).shuffle(schedule)  # noqa: S311 - deterministic evaluation design
    return tuple(schedule)


def aggregate_benchmark(
    cases: Sequence[BenchmarkCase],
    observations: Sequence[BenchmarkObservation],
    *,
    repetitions: int,
    confidence: float,
    bootstrap_resamples: int,
    seed: int,
    input_price_per_million: float,
    output_price_per_million: float,
) -> dict[str, Any]:
    """Aggregate quality, reliability, latency, usage, failures, and list-price cost."""

    if bootstrap_resamples < 1_000:
        raise ValueError("at least 1,000 bootstrap resamples are required")
    expected = len(cases) * repetitions
    if len(observations) != expected:
        raise ValueError(f"expected {expected} observations, received {len(observations)}")
    by_case: dict[str, list[BenchmarkObservation]] = defaultdict(list)
    for observation in observations:
        by_case[observation.case_id].append(observation)

    majority_threshold = repetitions // 2 + 1
    case_results: list[dict[str, Any]] = []
    category_totals: Counter[str] = Counter()
    category_successes: Counter[str] = Counter()
    consistent_cases = 0
    for case in cases:
        rows = by_case[case.identifier]
        if len(rows) != repetitions:
            raise ValueError(f"case {case.identifier} does not have {repetitions} observations")
        successes = sum(row.correct for row in rows)
        majority_correct = successes >= majority_threshold
        completed = [row.normalized_response for row in rows if row.status == "completed"]
        fully_consistent = len(completed) == repetitions and len(set(completed)) == 1
        consistent_cases += fully_consistent
        category_totals[case.category] += 1
        category_successes[case.category] += majority_correct
        case_results.append(
            {
                "case_id": case.identifier,
                "category": case.category,
                "correct_repetitions": successes,
                "majority_correct": majority_correct,
                "fully_consistent": fully_consistent,
            }
        )

    majority_successes = sum(result["majority_correct"] for result in case_results)
    completed_rows = [row for row in observations if row.status == "completed"]
    correct_requests = sum(row.correct for row in observations)
    failures = len(observations) - len(completed_rows)
    accuracy_interval = proportion_interval(
        majority_successes,
        len(cases),
        confidence=confidence,
        method="wilson",
    )
    failure_interval = proportion_interval(
        failures,
        len(observations),
        confidence=confidence,
        method="wilson",
    )

    latency_rows = [
        (row.case_id, float(row.latency_ms)) for row in completed_rows if row.latency_ms is not None
    ]
    latency = _latency_summary(
        latency_rows,
        confidence=confidence,
        resamples=bootstrap_resamples,
        seed=seed,
    )
    input_tokens = sum(row.input_tokens for row in observations)
    output_tokens = sum(row.output_tokens for row in observations)
    estimated_cost = (
        input_tokens * input_price_per_million + output_tokens * output_price_per_million
    ) / 1_000_000
    categories = {
        category: {
            "correct": category_successes[category],
            "cases": total,
            "majority_accuracy": category_successes[category] / total,
            "wilson_95": _interval_dict(
                proportion_interval(
                    category_successes[category],
                    total,
                    confidence=confidence,
                    method="wilson",
                )
            ),
        }
        for category, total in sorted(category_totals.items())
    }
    return {
        "primary": {
            "metric": "case-level majority normalized exact match",
            "correct": majority_successes,
            "cases": len(cases),
            "accuracy": majority_successes / len(cases),
            "wilson_95": _interval_dict(accuracy_interval),
        },
        "request_level": {
            "correct": correct_requests,
            "planned_requests": len(observations),
            "accuracy": correct_requests / len(observations),
            "note": "Descriptive only: repeated requests for a case are clustered.",
        },
        "reliability": {
            "fully_consistent_cases": consistent_cases,
            "cases": len(cases),
            "rate": consistent_cases / len(cases),
        },
        "failures": {
            "count": failures,
            "planned_requests": len(observations),
            "rate": failures / len(observations),
            "wilson_95": _interval_dict(failure_interval),
            "by_kind": dict(
                sorted(
                    Counter(
                        row.error_kind or "unknown"
                        for row in observations
                        if row.status != "completed"
                    ).items()
                )
            ),
        },
        "latency_ms": latency,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "estimated_standard_list_price_usd": round(estimated_cost, 8),
            "input_price_per_million_usd": input_price_per_million,
            "output_price_per_million_usd": output_price_per_million,
            "note": "Estimate from provider-reported tokens; actual billing may be free or differ.",
        },
        "categories": categories,
        "case_results": case_results,
    }


def observation_dict(observation: BenchmarkObservation) -> dict[str, Any]:
    """Serialize an observation without secret-bearing provider configuration."""

    return asdict(observation)


def _latency_summary(
    rows: Sequence[tuple[str, float]],
    *,
    confidence: float,
    resamples: int,
    seed: int,
) -> dict[str, Any]:
    if not rows:
        return {"completed_requests": 0, "p50": None, "p95": None}
    case_values: dict[str, list[float]] = defaultdict(list)
    for case_id, value in rows:
        if not math.isfinite(value) or value < 0:
            raise ValueError("latency values must be finite and non-negative")
        case_values[case_id].append(value)
    values = np.asarray([value for _, value in rows], dtype=np.float64)
    return {
        "completed_requests": len(values),
        "mean": round(float(np.mean(values)), 3),
        "p50": _cluster_quantile_interval(
            case_values,
            quantile=0.5,
            confidence=confidence,
            resamples=resamples,
            seed=seed,
        ),
        "p95": _cluster_quantile_interval(
            case_values,
            quantile=0.95,
            confidence=confidence,
            resamples=resamples,
            seed=seed + 1,
        ),
        "minimum": round(float(np.min(values)), 3),
        "maximum": round(float(np.max(values)), 3),
        "method": "percentile cluster bootstrap by benchmark case",
    }


def _cluster_quantile_interval(
    case_values: dict[str, list[float]],
    *,
    quantile: float,
    confidence: float,
    resamples: int,
    seed: int,
) -> dict[str, float]:
    clusters = sorted(case_values)
    generator = np.random.default_rng(seed)
    all_values = np.asarray(
        [value for cluster in clusters for value in case_values[cluster]],
        dtype=np.float64,
    )
    draws = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        selected = generator.choice(clusters, size=len(clusters), replace=True)
        sample = np.asarray(
            [value for cluster in selected for value in case_values[str(cluster)]],
            dtype=np.float64,
        )
        draws[index] = np.quantile(sample, quantile)
    alpha = 1 - confidence
    lower, upper = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return {
        "estimate": round(float(np.quantile(all_values, quantile)), 3),
        "lower": round(float(lower), 3),
        "upper": round(float(upper), 3),
    }


def _interval_dict(interval: Any) -> dict[str, Any]:
    return {
        "lower": round(interval.lower, 6),
        "upper": round(interval.upper, 6),
        "confidence": interval.confidence,
        "method": interval.method,
        "effective_sample_size": interval.effective_sample_size,
        "warnings": [warning.code.value for warning in interval.warnings],
    }
