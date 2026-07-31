"""Repeatable local performance scenarios with intentionally conservative ceilings."""

from __future__ import annotations

import time
import uuid

import pytest
from eval_platform_application.comparisons import SampleMetric, compare_metric
from eval_platform_domain.canonicalization import canonical_bytes
from eval_platform_evaluators.pairwise import balanced_pair_assignments
from eval_platform_schemas.analysis import MissingDataPolicy

pytestmark = pytest.mark.performance


def test_canonicalization_of_ten_thousand_records_is_bounded() -> None:
    records = [
        {
            "key": f"record-{index:05d}",
            "payload": {"question": f"Question {index}", "weight": index / 7},
            "metadata": {"language": "en", "bucket": index % 20},
        }
        for index in range(10_000)
    ]
    started = time.perf_counter()
    result = canonical_bytes(records)
    elapsed = time.perf_counter() - started
    assert len(result) > 500_000
    assert elapsed < 10, f"canonicalization took {elapsed:.3f}s; target is under 10s"


def test_balanced_schedule_avoids_unbounded_pair_fanout() -> None:
    started = time.perf_counter()
    assignments = balanced_pair_assignments(
        design_id=uuid.uuid4(),
        record_keys=[f"record-{index}" for index in range(2_000)],
        variant_ids=["a", "b", "c", "d"],
        judge_slots=2,
        repetitions=1,
        seed=91,
        sample_size=500,
    )
    elapsed = time.perf_counter() - started
    assert len(assignments) == 500
    assert elapsed < 10, f"pair scheduling took {elapsed:.3f}s; target is under 10s"


def test_paired_comparison_handles_five_thousand_samples_without_quadratic_growth() -> None:
    baseline = {
        str(index): SampleMetric(str(index), "succeeded", float(index % 2))
        for index in range(5_000)
    }
    candidate = {
        str(index): SampleMetric(str(index), "succeeded", float((index + index // 5) % 2))
        for index in range(5_000)
    }
    started = time.perf_counter()
    result = compare_metric(
        metric_identifier="accuracy",
        metric_version="1.0.0",
        baseline=baseline,
        candidate=candidate,
        confidence=0.95,
        bootstrap_method="percentile",
        bootstrap_resamples=200,
        test="paired_t",
        seed=44,
        missing_data_policy=MissingDataPolicy.AVAILABLE_PAIRS,
        practical_difference=0.01,
        top_changed_examples=20,
    )
    elapsed = time.perf_counter() - started
    assert result.paired_count == 5_000
    assert elapsed < 15, f"paired comparison took {elapsed:.3f}s; target is under 15s"
