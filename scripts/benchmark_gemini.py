"""Run a bounded Gemini benchmark through the provider abstraction."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from eval_platform_application.benchmarking import (
    BenchmarkObservation,
    aggregate_benchmark,
    benchmark_schedule,
    is_correct,
    load_benchmark_cases,
    normalize_benchmark_answer,
    observation_dict,
)
from eval_platform_providers import GenerationRequest, ProviderError
from eval_platform_providers.http import OpenAICompatibleProvider

BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
PROMPT_PREFIX = (
    "Answer the task below. Return only the answer, with no explanation, label, "
    "quotation marks, or Markdown.\n\nTask: "
)


def parse_args() -> argparse.Namespace:
    """Parse a bounded, reproducible benchmark configuration."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("examples/benchmarks/core-v1.jsonl"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gemini-3.6-flash")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--max-output-tokens", type=int, default=256)
    parser.add_argument(
        "--reasoning-effort",
        choices=("minimal", "low", "medium", "high"),
        default="minimal",
    )
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--minimum-interval-seconds", type=float, default=1.5)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--bootstrap-resamples", type=int, default=10_000)
    parser.add_argument("--input-price-per-million", type=float, default=1.50)
    parser.add_argument("--output-price-per-million", type=float, default=7.50)
    args = parser.parse_args()
    if args.repetitions < 1 or args.max_attempts < 1:
        parser.error("repetitions and max-attempts must be positive")
    if args.max_output_tokens < 1 or args.timeout_seconds <= 0:
        parser.error("token and timeout limits must be positive")
    if args.minimum_interval_seconds < 0:
        parser.error("minimum interval cannot be negative")
    if args.bootstrap_resamples < 1_000:
        parser.error("bootstrap resamples must be at least 1,000")
    return args


async def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute sequential logical requests with bounded retry and full denominators."""

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY must be supplied through the environment")
    cases, dataset_hash = load_benchmark_cases(args.dataset)
    started = datetime.now(UTC)
    wall_start = time.perf_counter()
    observations: list[BenchmarkObservation] = []
    model_names: set[str] = set()
    timeout = httpx.Timeout(args.timeout_seconds)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        provider = OpenAICompatibleProvider(
            identifier="google/gemini-openai-compatible",
            base_url=BASE_URL,
            api_key=api_key,
            timeout_seconds=args.timeout_seconds,
            client=client,
        )
        schedule = benchmark_schedule(cases, repetitions=args.repetitions, seed=args.seed)
        for index, (case, repetition) in enumerate(schedule, start=1):
            request_started = time.perf_counter()
            attempts = 0
            observation: BenchmarkObservation | None = None
            while attempts < args.max_attempts:
                attempts += 1
                try:
                    response = await provider.generate(
                        GenerationRequest(
                            model=args.model,
                            prompt=f"{PROMPT_PREFIX}{case.prompt}",
                            temperature=None,
                            max_output_tokens=args.max_output_tokens,
                            reasoning_effort=args.reasoning_effort,
                        )
                    )
                    latency_ms = (time.perf_counter() - request_started) * 1_000
                    model_names.add(response.model)
                    observation = BenchmarkObservation(
                        case_id=case.identifier,
                        category=case.category,
                        repetition=repetition,
                        status="completed",
                        response=response.text,
                        normalized_response=normalize_benchmark_answer(response.text),
                        correct=is_correct(response.text, case.accepted_answers),
                        latency_ms=round(latency_ms, 3),
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        attempts=attempts,
                        provider_request_id=response.provider_request_id,
                    )
                    break
                except ProviderError as error:
                    if error.retryable and attempts < args.max_attempts:
                        retry_after = error.retry_after_seconds or min(2 ** (attempts - 1), 20)
                        await asyncio.sleep(max(0.0, retry_after))
                        continue
                    observation = BenchmarkObservation(
                        case_id=case.identifier,
                        category=case.category,
                        repetition=repetition,
                        status="failed",
                        response=None,
                        normalized_response=None,
                        correct=False,
                        latency_ms=round((time.perf_counter() - request_started) * 1_000, 3),
                        input_tokens=0,
                        output_tokens=0,
                        attempts=attempts,
                        error_kind=error.kind.value,
                    )
                    break
            if observation is None:
                raise RuntimeError("bounded request loop ended without an observation")
            observations.append(observation)
            print(
                f"[{index:02d}/{len(schedule)}] {case.identifier} "
                f"status={observation.status} correct={observation.correct} "
                f"attempts={observation.attempts}",
                flush=True,
            )
            elapsed = time.perf_counter() - request_started
            delay = args.minimum_interval_seconds - elapsed
            if delay > 0 and index < len(schedule):
                await asyncio.sleep(delay)

    aggregate = aggregate_benchmark(
        cases,
        observations,
        repetitions=args.repetitions,
        confidence=0.95,
        bootstrap_resamples=args.bootstrap_resamples,
        seed=args.seed,
        input_price_per_million=args.input_price_per_million,
        output_price_per_million=args.output_price_per_million,
    )
    completed = datetime.now(UTC)
    report: dict[str, Any] = {
        "schema_version": "gemini-benchmark/1",
        "benchmark": {
            "name": "Synthetic Core Exact-Answer Benchmark",
            "dataset_path": args.dataset.as_posix(),
            "dataset_sha256": dataset_hash,
            "case_count": len(cases),
            "categories": sorted({case.category for case in cases}),
            "repetitions": args.repetitions,
            "planned_requests": len(cases) * args.repetitions,
            "schedule_seed": args.seed,
            "normalization": (
                "NFC, trim, whitespace collapse, case-fold, code-fence and "
                "final punctuation removal"
            ),
        },
        "system": {
            "provider": "Google Gemini API via OpenAI-compatible REST",
            "base_url": BASE_URL,
            "requested_model": args.model,
            "reported_models": sorted(model_names),
            "temperature": None,
            "reasoning_effort": args.reasoning_effort,
            "max_output_tokens": args.max_output_tokens,
            "timeout_seconds": args.timeout_seconds,
            "maximum_attempts": args.max_attempts,
            "concurrency": 1,
            "minimum_request_interval_seconds": args.minimum_interval_seconds,
        },
        "execution": {
            "started_at": started.isoformat(),
            "completed_at": completed.isoformat(),
            "wall_duration_seconds": round(time.perf_counter() - wall_start, 3),
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "results": aggregate,
        "observations": [observation_dict(observation) for observation in observations],
        "limitations": [
            "The 24-case synthetic set is a smoke benchmark, not a broad capability claim.",
            "Exact match measures constrained answers and does not assess open-ended quality.",
            "The API does not promise bit-for-bit determinism for repeated fixed-parameter calls.",
            (
                "Latency is client-observed sequential latency from one location, "
                "not capacity throughput."
            ),
            (
                "The repeated observations are clustered by case; the primary interval "
                "uses one majority outcome per case."
            ),
            "List-price cost is estimated from reported tokens and may differ from actual billing.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    """Run the benchmark and print only non-sensitive aggregate output."""

    args = parse_args()
    try:
        report = asyncio.run(run(args))
    except (OSError, ValueError, RuntimeError) as error:
        print(f"benchmark failed: {error}", file=sys.stderr)
        return 2
    primary = report["results"]["primary"]
    latency = report["results"]["latency_ms"]
    failures = report["results"]["failures"]
    usage = report["results"]["usage"]
    print(
        json.dumps(
            {
                "accuracy": primary["accuracy"],
                "accuracy_wilson_95": primary["wilson_95"],
                "failures": failures["count"],
                "latency_p50_ms": latency["p50"],
                "latency_p95_ms": latency["p95"],
                "total_tokens": usage["total_tokens"],
                "estimated_standard_list_price_usd": usage["estimated_standard_list_price_usd"],
                "output": args.output.as_posix(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
