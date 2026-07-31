"""Paired hypothesis and equivalence tests with explicit tie handling."""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from scipy import stats

from eval_platform_statistics.models import (
    AnalysisWarning,
    HypothesisTest,
    WarningCode,
    paired_values,
    sample_warnings,
)


def paired_t_test(
    left: Sequence[float],
    right: Sequence[float],
    *,
    alternative: str = "two-sided",
) -> HypothesisTest:
    """Paired Student t-test of a zero mean difference."""

    left_values, right_values = paired_values(left, right, minimum=2)
    differences = np.asarray(right_values) - np.asarray(left_values)
    _alternative(alternative)
    if np.var(differences) == 0:
        statistic = math.inf if float(np.mean(differences)) else 0.0
        p_value = 0.0 if statistic else 1.0
    else:
        result = stats.ttest_rel(right_values, left_values, alternative=alternative)
        statistic, p_value = float(result.statistic), float(result.pvalue)
    return HypothesisTest(
        statistic,
        p_value,
        "paired_t",
        alternative,
        len(left_values),
        len(left_values),
        sample_warnings(differences.tolist()),
    )


def wilcoxon_signed_rank_test(
    left: Sequence[float],
    right: Sequence[float],
    *,
    alternative: str = "two-sided",
) -> HypothesisTest:
    """Wilcoxon signed-rank test; exact zeros are discarded explicitly."""

    left_values, right_values = paired_values(left, right, minimum=1)
    _alternative(alternative)
    differences = np.asarray(right_values) - np.asarray(left_values)
    nonzero = differences[differences != 0]
    warnings = list(sample_warnings(nonzero.tolist()))
    if len(nonzero) == 0:
        warnings.append(AnalysisWarning(WarningCode.ALL_TIES, "all paired differences are zero"))
        return HypothesisTest(
            0.0,
            1.0,
            "wilcoxon_signed_rank",
            alternative,
            len(differences),
            0,
            tuple(warnings),
        )
    result = stats.wilcoxon(
        nonzero,
        alternative=alternative,
        zero_method="wilcox",
        method="auto",
    )
    return HypothesisTest(
        float(result.statistic),
        float(result.pvalue),
        "wilcoxon_signed_rank",
        alternative,
        len(differences),
        len(nonzero),
        tuple(warnings),
    )


def sign_test(
    left: Sequence[float],
    right: Sequence[float],
    *,
    alternative: str = "two-sided",
) -> HypothesisTest:
    """Exact sign test excluding tied pairs from the binomial denominator."""

    left_values, right_values = paired_values(left, right, minimum=1)
    _alternative(alternative)
    differences = np.asarray(right_values) - np.asarray(left_values)
    positives = int(np.sum(differences > 0))
    negatives = int(np.sum(differences < 0))
    effective = positives + negatives
    warnings = list(sample_warnings(differences[differences != 0].tolist()))
    if effective == 0:
        warnings.append(AnalysisWarning(WarningCode.ALL_TIES, "all paired differences are zero"))
        p_value = 1.0
    else:
        p_value = float(stats.binomtest(positives, effective, 0.5, alternative=alternative).pvalue)
    return HypothesisTest(
        float(positives),
        p_value,
        "exact_sign",
        alternative,
        len(differences),
        effective,
        tuple(warnings),
    )


def mcnemar_test(
    left_correct: Sequence[bool],
    right_correct: Sequence[bool],
    *,
    alternative: str = "two-sided",
) -> HypothesisTest:
    """Exact McNemar test using only discordant paired binary outcomes."""

    if len(left_correct) != len(right_correct) or not left_correct:
        raise ValueError("paired binary outcomes must be equally sized and non-empty")
    _alternative(alternative)
    left_only = sum(
        left and not right for left, right in zip(left_correct, right_correct, strict=True)
    )
    right_only = sum(
        right and not left for left, right in zip(left_correct, right_correct, strict=True)
    )
    discordant = left_only + right_only
    warnings: list[AnalysisWarning] = []
    if discordant == 0:
        warnings.append(
            AnalysisWarning(WarningCode.DEGENERATE_OUTCOME, "there are no discordant pairs")
        )
        p_value = 1.0
    else:
        p_value = float(
            stats.binomtest(right_only, discordant, 0.5, alternative=alternative).pvalue
        )
    return HypothesisTest(
        float(right_only),
        p_value,
        "exact_mcnemar",
        alternative,
        len(left_correct),
        discordant,
        tuple(warnings),
    )


def permutation_test(
    left: Sequence[float],
    right: Sequence[float],
    *,
    alternative: str = "two-sided",
    permutations: int = 20_000,
    seed: int = 0,
) -> HypothesisTest:
    """Paired randomization test by swapping signs within matched records."""

    left_values, right_values = paired_values(left, right, minimum=1)
    _alternative(alternative)
    differences = np.asarray(right_values) - np.asarray(left_values)
    nonzero = differences[differences != 0]
    warnings = list(sample_warnings(nonzero.tolist()))
    if len(nonzero) == 0:
        warnings.append(AnalysisWarning(WarningCode.ALL_TIES, "all paired differences are zero"))
        return HypothesisTest(
            0.0,
            1.0,
            "paired_permutation_exact",
            alternative,
            len(differences),
            0,
            tuple(warnings),
        )
    observed = float(np.mean(nonzero))
    if len(nonzero) <= 20:
        statistics = np.fromiter(
            (
                float(np.mean(nonzero * np.asarray(signs)))
                for signs in itertools.product((-1, 1), repeat=len(nonzero))
            ),
            dtype=np.float64,
        )
        p_value = _tail_probability(statistics, observed, alternative, add_one=False)
        method = "paired_permutation_exact"
    else:
        if permutations < 1000:
            raise ValueError("at least 1000 random permutations are required")
        generator = np.random.default_rng(seed)
        signs = generator.choice((-1, 1), size=(permutations, len(nonzero)))
        statistics = np.mean(signs * nonzero, axis=1)
        p_value = _tail_probability(statistics, observed, alternative, add_one=True)
        method = "paired_permutation_monte_carlo"
    return HypothesisTest(
        observed,
        p_value,
        method,
        alternative,
        len(differences),
        len(nonzero),
        tuple(warnings),
    )


def paired_bootstrap_test(
    left: Sequence[float],
    right: Sequence[float],
    *,
    alternative: str = "two-sided",
    resamples: int = 20_000,
    seed: int = 0,
) -> HypothesisTest:
    """Centered paired-bootstrap test of a zero mean difference."""

    left_values, right_values = paired_values(left, right, minimum=2)
    _alternative(alternative)
    if resamples < 1000:
        raise ValueError("at least 1000 bootstrap resamples are required")
    differences = np.asarray(right_values) - np.asarray(left_values)
    observed = float(np.mean(differences))
    centered = differences - observed
    generator = np.random.default_rng(seed)
    statistics = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        statistics[index] = float(
            np.mean(generator.choice(centered, size=len(centered), replace=True))
        )
    return HypothesisTest(
        observed,
        _tail_probability(statistics, observed, alternative, add_one=True),
        "paired_bootstrap_test",
        alternative,
        len(differences),
        len(differences),
        sample_warnings(differences.tolist()),
    )


def pairwise_binomial_test(
    wins: int,
    losses: int,
    ties: int = 0,
    *,
    alternative: str = "two-sided",
) -> HypothesisTest:
    """Exact preference test with ties reported but excluded from this null model."""

    _alternative(alternative)
    if min(wins, losses, ties) < 0 or wins + losses + ties == 0:
        raise ValueError("pairwise counts must be non-negative and not all zero")
    effective = wins + losses
    warnings: list[AnalysisWarning] = []
    if effective == 0:
        warnings.append(AnalysisWarning(WarningCode.ALL_TIES, "all pairwise outcomes are ties"))
        p_value = 1.0
    else:
        p_value = float(stats.binomtest(wins, effective, 0.5, alternative=alternative).pvalue)
    return HypothesisTest(
        float(wins),
        p_value,
        "pairwise_exact_binomial_ties_excluded",
        alternative,
        wins + losses + ties,
        effective,
        tuple(warnings),
    )


@dataclass(frozen=True, slots=True)
class EquivalenceTest:
    """Two one-sided tests for a prespecified practical equivalence margin."""

    mean_difference: float
    lower_margin: float
    upper_margin: float
    lower_p_value: float
    upper_p_value: float
    alpha: float
    equivalent: bool
    sample_size: int
    warnings: tuple[AnalysisWarning, ...]


def paired_tost(
    left: Sequence[float],
    right: Sequence[float],
    *,
    lower_margin: float,
    upper_margin: float,
    alpha: float = 0.05,
) -> EquivalenceTest:
    """TOST equivalence test for paired continuous measurements."""

    if lower_margin >= upper_margin or not lower_margin < 0 < upper_margin:
        raise ValueError("equivalence margins must straddle zero")
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must be between zero and 0.5")
    left_values, right_values = paired_values(left, right, minimum=2)
    differences = np.asarray(right_values) - np.asarray(left_values)
    mean = float(np.mean(differences))
    standard_error = float(stats.sem(differences))
    if standard_error == 0:
        lower_p = 0.0 if mean > lower_margin else 1.0
        upper_p = 0.0 if mean < upper_margin else 1.0
    else:
        degrees = len(differences) - 1
        lower_t = (mean - lower_margin) / standard_error
        upper_t = (mean - upper_margin) / standard_error
        lower_p = float(stats.t.sf(lower_t, degrees))
        upper_p = float(stats.t.cdf(upper_t, degrees))
    return EquivalenceTest(
        mean,
        lower_margin,
        upper_margin,
        lower_p,
        upper_p,
        alpha,
        max(lower_p, upper_p) < alpha,
        len(differences),
        sample_warnings(differences.tolist()),
    )


def _tail_probability(
    null_statistics: np.ndarray,
    observed: float,
    alternative: str,
    *,
    add_one: bool,
) -> float:
    if alternative == "two-sided":
        exceedances = int(np.sum(np.abs(null_statistics) >= abs(observed)))
    elif alternative == "greater":
        exceedances = int(np.sum(null_statistics >= observed))
    else:
        exceedances = int(np.sum(null_statistics <= observed))
    adjustment = 1 if add_one else 0
    return (exceedances + adjustment) / (len(null_statistics) + adjustment)


def _alternative(alternative: str) -> None:
    if alternative not in {"two-sided", "less", "greater"}:
        raise ValueError("alternative must be two-sided, less, or greater")
