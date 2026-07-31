"""Pure paired experiment comparison and practical interpretation."""

from __future__ import annotations

import statistics
from collections.abc import Mapping
from dataclasses import dataclass

from eval_platform_schemas.analysis import (
    IntervalRead,
    MetricComparisonRead,
    MissingDataPolicy,
)
from eval_platform_statistics.effects import paired_continuous_effects
from eval_platform_statistics.models import HypothesisTest, align_pairs


@dataclass(frozen=True, slots=True)
class SampleMetric:
    """One per-record metric state; failures and missingness are distinct."""

    record_id: str
    status: str
    value: float | None


def compare_metric(
    *,
    metric_identifier: str,
    metric_version: str,
    baseline: Mapping[str, SampleMetric],
    candidate: Mapping[str, SampleMetric],
    confidence: float,
    bootstrap_method: str,
    bootstrap_resamples: int,
    test: str,
    seed: int,
    missing_data_policy: MissingDataPolicy,
    practical_difference: float,
    top_changed_examples: int,
) -> MetricComparisonRead:
    """Compute a record-paired comparison with visible failure denominators."""

    baseline_values = _analysis_values(baseline, missing_data_policy)
    candidate_values = _analysis_values(candidate, missing_data_policy)
    aligned = align_pairs(baseline_values, candidate_values)
    if aligned.effective_sample_size < 2:
        raise ValueError("at least two finite paired metric results are required")
    effects = paired_continuous_effects(aligned.left, aligned.right)
    from eval_platform_statistics.intervals import paired_bootstrap_interval

    interval = paired_bootstrap_interval(
        aligned.left,
        aligned.right,
        confidence=confidence,
        method=bootstrap_method,
        resamples=bootstrap_resamples,
        seed=seed,
    )
    test_result = _test(test, aligned.left, aligned.right, bootstrap_resamples, seed)
    changes: list[dict[str, str | float]] = sorted(
        (
            {
                "record_id": record_id,
                "baseline": left,
                "candidate": right,
                "difference": right - left,
            }
            for record_id, left, right in zip(
                aligned.record_ids,
                aligned.left,
                aligned.right,
                strict=True,
            )
        ),
        key=lambda item: (float(item["difference"]), str(item["record_id"])),
    )
    return MetricComparisonRead(
        metric_identifier=metric_identifier,
        metric_version=metric_version,
        baseline_mean=statistics.fmean(aligned.left),
        candidate_mean=statistics.fmean(aligned.right),
        mean_difference=effects.mean_difference,
        median_difference=effects.median_difference,
        relative_improvement=effects.relative_improvement,
        probability_of_superiority=effects.probability_of_superiority,
        standardized_mean_difference=effects.standardized_mean_difference_dz,
        confidence_interval=IntervalRead(
            lower=interval.lower,
            upper=interval.upper,
            confidence=interval.confidence,
            method=interval.method,
        ),
        p_value=test_result.p_value,
        test_method=test_result.method,
        total_union_count=aligned.union_size,
        paired_count=aligned.effective_sample_size,
        missing_baseline_count=aligned.missing_left,
        missing_candidate_count=aligned.missing_right,
        failed_baseline_count=sum(sample.status == "failed" for sample in baseline.values()),
        failed_candidate_count=sum(sample.status == "failed" for sample in candidate.values()),
        practical_interpretation=_interpret(
            effects.mean_difference,
            interval.lower,
            interval.upper,
            test_result.p_value,
            1 - confidence,
            practical_difference,
        ),
        warnings=[
            {"code": warning.code, "message": warning.message}
            for warning in (*aligned.warnings, *interval.warnings, *test_result.warnings)
        ],
        largest_improvements=(
            list(reversed(changes[-top_changed_examples:])) if top_changed_examples else []
        ),
        largest_regressions=changes[:top_changed_examples] if top_changed_examples else [],
    )


def _analysis_values(
    samples: Mapping[str, SampleMetric],
    policy: MissingDataPolicy,
) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for record_id, sample in samples.items():
        if sample.status == "succeeded" and sample.value is not None:
            values[record_id] = sample.value
        elif policy == MissingDataPolicy.FAILURES_AS_ZERO and sample.status == "failed":
            values[record_id] = 0.0
        else:
            values[record_id] = None
    return values


def _test(
    identifier: str,
    baseline: tuple[float, ...],
    candidate: tuple[float, ...],
    resamples: int,
    seed: int,
) -> HypothesisTest:
    from eval_platform_statistics.hypothesis import (
        paired_bootstrap_test,
        paired_t_test,
        permutation_test,
        sign_test,
        wilcoxon_signed_rank_test,
    )

    if identifier == "paired_t":
        return paired_t_test(baseline, candidate)
    if identifier == "wilcoxon":
        return wilcoxon_signed_rank_test(baseline, candidate)
    if identifier == "sign":
        return sign_test(baseline, candidate)
    if identifier == "paired_bootstrap":
        return paired_bootstrap_test(
            baseline,
            candidate,
            resamples=max(1000, resamples),
            seed=seed,
        )
    return permutation_test(
        baseline,
        candidate,
        permutations=max(1000, resamples),
        seed=seed,
    )


def _interpret(
    difference: float,
    lower: float,
    upper: float,
    p_value: float,
    alpha: float,
    practical_difference: float,
) -> str:
    significant = p_value < alpha
    meaningful = abs(difference) >= practical_difference
    if upper <= -practical_difference and practical_difference > 0:
        return "evidence_of_meaningful_regression"
    if significant and meaningful:
        return "statistically_significant_and_practically_meaningful"
    if significant:
        return "statistically_significant_but_practically_small"
    if lower >= -practical_difference and upper <= practical_difference:
        return "compatible_with_configured_tolerance"
    return "not_statistically_conclusive"
