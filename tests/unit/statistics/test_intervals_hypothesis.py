"""Numerical, edge-case, and reproducibility tests for inferential procedures."""

from __future__ import annotations

import math

import numpy as np
import pytest
from eval_platform_statistics.hypothesis import (
    mcnemar_test,
    paired_bootstrap_test,
    paired_t_test,
    paired_tost,
    pairwise_binomial_test,
    permutation_test,
    sign_test,
    wilcoxon_signed_rank_test,
)
from eval_platform_statistics.intervals import (
    bootstrap_interval,
    cluster_bootstrap_interval,
    mean_t_interval,
    paired_bootstrap_interval,
    proportion_interval,
    quantile_bootstrap_interval,
    stratified_bootstrap_interval,
)
from eval_platform_statistics.models import WarningCode, align_pairs
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy import stats


def test_wilson_interval_matches_hand_calculated_example() -> None:
    interval = proportion_interval(5, 10, confidence=0.95, method="wilson")
    assert interval.estimate == 0.5
    assert interval.lower == pytest.approx(0.236593, abs=1e-6)
    assert interval.upper == pytest.approx(0.763407, abs=1e-6)
    exact = proportion_interval(0, 10, method="exact")
    assert exact.lower == 0
    assert exact.upper == pytest.approx(0.308497, abs=1e-6)
    assert WarningCode.DEGENERATE_OUTCOME in {warning.code for warning in exact.warnings}


def test_student_interval_and_paired_t_match_scipy() -> None:
    sample = [1.2, 2.4, 3.1, 2.8, 4.0]
    interval = mean_t_interval(sample)
    expected = stats.t.interval(0.95, len(sample) - 1, loc=np.mean(sample), scale=stats.sem(sample))
    assert (interval.lower, interval.upper) == pytest.approx(expected)
    baseline = [1.0, 2.0, 3.0, 4.0, 5.0]
    candidate = [1.1, 2.4, 2.9, 4.8, 5.4]
    result = paired_t_test(baseline, candidate)
    expected_test = stats.ttest_rel(candidate, baseline)
    assert result.statistic == pytest.approx(expected_test.statistic)
    assert result.p_value == pytest.approx(expected_test.pvalue)


def test_bootstrap_variants_are_seeded_and_ordered() -> None:
    values = [1, 2, 2, 3, 5, 8, 13, 21]
    for method in ("percentile", "basic", "bca"):
        first = bootstrap_interval(values, method=method, resamples=800, seed=42)
        second = bootstrap_interval(values, method=method, resamples=800, seed=42)
        assert first == second
        assert first.lower <= first.estimate <= first.upper
    median = quantile_bootstrap_interval(
        values,
        quantile=0.5,
        resamples=800,
        seed=6,
    )
    assert median.estimate == 4


def test_paired_bootstrap_preserves_shared_record_signal() -> None:
    baseline = [100 + index for index in range(30)]
    candidate = [value + ((index % 3) - 1) * 0.1 + 0.5 for index, value in enumerate(baseline)]
    interval = paired_bootstrap_interval(
        baseline,
        candidate,
        resamples=1000,
        seed=17,
    )
    assert interval.method == "paired_percentile_bootstrap"
    assert interval.estimate == pytest.approx(0.5)
    assert interval.upper - interval.lower < 0.08


def test_stratified_and_cluster_bootstrap_report_effective_sizes() -> None:
    values = [1, 2, 3, 4, 10, 11, 12, 13]
    stratified = stratified_bootstrap_interval(
        values,
        ["easy"] * 4 + ["hard"] * 4,
        resamples=500,
        seed=8,
    )
    clustered = cluster_bootstrap_interval(
        values,
        ["one"] * 2 + ["two"] * 2 + ["three"] * 2 + ["four"] * 2,
        resamples=500,
        seed=8,
    )
    assert stratified.effective_sample_size == 8
    assert clustered.effective_sample_size == 4
    assert WarningCode.TOO_FEW_CLUSTERS in {warning.code for warning in clustered.warnings}


def test_alignment_accounts_for_every_missing_or_invalid_record() -> None:
    aligned = align_pairs(
        {"a": 1, "b": None, "c": 3, "d": math.nan},
        {"a": 2, "b": 2, "d": 4, "e": 5},
        excessive_missingness_threshold=0.1,
    )
    assert aligned.record_ids == ("a",)
    assert aligned.union_size == 5
    assert aligned.missing_left == 2
    assert aligned.missing_right == 1
    assert aligned.non_finite == 1
    assert WarningCode.EXCESSIVE_MISSINGNESS in {warning.code for warning in aligned.warnings}


def test_nonparametric_tests_handle_ties_and_small_samples() -> None:
    all_ties = wilcoxon_signed_rank_test([1, 2], [1, 2])
    assert all_ties.p_value == 1
    assert all_ties.effective_sample_size == 0
    sign = sign_test([0, 0, 0, 0, 0], [1, 1, 1, 0, -1])
    assert sign.effective_sample_size == 4
    assert sign.p_value == pytest.approx(0.625)
    permutation = permutation_test([0, 0, 0], [1, 2, 3])
    assert permutation.method == "paired_permutation_exact"
    assert permutation.p_value == pytest.approx(0.25)


def test_binary_pairwise_bootstrap_and_equivalence_procedures() -> None:
    mcnemar = mcnemar_test(
        [True, True, True, True, True, True, True, False],
        [False, False, False, False, False, False, False, True],
    )
    assert mcnemar.effective_sample_size == 8
    assert mcnemar.p_value == pytest.approx(0.0703125)
    preference = pairwise_binomial_test(8, 2, 4)
    assert preference.sample_size == 14
    assert preference.effective_sample_size == 10
    boot = paired_bootstrap_test(
        [1, 2, 3, 4, 5],
        [1.1, 2.2, 3.1, 4.4, 5.2],
        resamples=1000,
        seed=2,
    )
    assert 0 <= boot.p_value <= 1
    equivalent = paired_tost(
        [1, 2, 3, 4, 5, 6],
        [1.01, 2.01, 3.01, 4.01, 5.01, 6.01],
        lower_margin=-0.1,
        upper_margin=0.1,
    )
    assert equivalent.equivalent is True


@settings(max_examples=30, deadline=None)
@given(
    successes=st.integers(min_value=0, max_value=100),
    total=st.integers(min_value=1, max_value=100),
)
def test_proportion_interval_bounds_are_ordered(successes: int, total: int) -> None:
    bounded_successes = min(successes, total)
    interval = proportion_interval(bounded_successes, total)
    assert 0 <= interval.lower <= interval.upper <= 1
    assert interval.lower <= interval.estimate <= interval.upper


def test_wilson_simulation_has_reasonable_frequentist_coverage() -> None:
    generator = np.random.default_rng(20260730)
    covered = 0
    repetitions = 600
    for successes in generator.binomial(80, 0.3, size=repetitions):
        interval = proportion_interval(int(successes), 80)
        covered += interval.lower <= 0.3 <= interval.upper
    coverage = covered / repetitions
    assert 0.91 <= coverage <= 0.98
