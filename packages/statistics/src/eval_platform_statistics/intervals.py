"""Confidence intervals for scalar, proportion, paired, stratified, and clustered data."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Sequence

import numpy as np
from scipy import stats

from eval_platform_statistics.models import (
    AnalysisWarning,
    ConfidenceInterval,
    WarningCode,
    finite_values,
    paired_values,
    sample_warnings,
)

Statistic = Callable[[np.ndarray], float]


def mean_t_interval(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
) -> ConfidenceInterval:
    """Student t interval for an arithmetic mean."""

    sample = np.asarray(finite_values(values, minimum=2), dtype=np.float64)
    _confidence(confidence)
    estimate = float(np.mean(sample))
    standard_error = float(stats.sem(sample))
    if standard_error == 0:
        lower = upper = estimate
    else:
        critical = float(stats.t.ppf((1 + confidence) / 2, len(sample) - 1))
        lower, upper = estimate - critical * standard_error, estimate + critical * standard_error
    return ConfidenceInterval(
        estimate,
        lower,
        upper,
        confidence,
        "student_t",
        len(sample),
        len(sample),
        warnings=sample_warnings(sample.tolist()),
    )


def proportion_interval(
    successes: int,
    total: int,
    *,
    confidence: float = 0.95,
    method: str = "wilson",
) -> ConfidenceInterval:
    """Wilson or exact Clopper-Pearson interval for a binomial proportion."""

    _confidence(confidence)
    if total < 1 or not 0 <= successes <= total:
        raise ValueError("successes must be between zero and a positive total")
    estimate = successes / total
    alpha = 1 - confidence
    warnings: list[AnalysisWarning] = []
    if total < 30:
        warnings.append(
            AnalysisWarning(WarningCode.VERY_SMALL_SAMPLE, f"only {total} trials are available")
        )
    if successes in {0, total}:
        warnings.append(
            AnalysisWarning(
                WarningCode.DEGENERATE_OUTCOME,
                "the observed proportion is at a boundary",
            )
        )
    if method == "wilson":
        z = float(stats.norm.ppf(1 - alpha / 2))
        denominator = 1 + (z * z / total)
        center = (estimate + z * z / (2 * total)) / denominator
        radius = (
            z
            * math.sqrt(estimate * (1 - estimate) / total + z * z / (4 * total * total))
            / denominator
        )
        lower = min(estimate, max(0.0, center - radius))
        upper = max(estimate, min(1.0, center + radius))
    elif method == "exact":
        lower = (
            0.0
            if successes == 0
            else float(stats.beta.ppf(alpha / 2, successes, total - successes + 1))
        )
        upper = (
            1.0
            if successes == total
            else float(stats.beta.ppf(1 - alpha / 2, successes + 1, total - successes))
        )
    else:
        raise ValueError("proportion interval method must be 'wilson' or 'exact'")
    return ConfidenceInterval(
        estimate,
        lower,
        upper,
        confidence,
        method,
        total,
        total,
        warnings=tuple(warnings),
    )


def bootstrap_interval(
    values: Sequence[float],
    *,
    statistic: Statistic | None = None,
    confidence: float = 0.95,
    method: str = "percentile",
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Percentile, basic, or bias-corrected and accelerated bootstrap interval."""

    sample = np.asarray(finite_values(values, minimum=2), dtype=np.float64)
    _bootstrap_arguments(confidence, resamples, seed)
    function = statistic or _mean
    estimate = float(function(sample))
    generator = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        draws[index] = function(generator.choice(sample, size=len(sample), replace=True))
    alpha = 1 - confidence
    if method == "percentile":
        lower, upper = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    elif method == "basic":
        high, low = np.quantile(draws, [1 - alpha / 2, alpha / 2])
        lower, upper = 2 * estimate - high, 2 * estimate - low
    elif method == "bca":
        lower, upper = _bca_limits(sample, draws, function, estimate, alpha)
    else:
        raise ValueError("bootstrap method must be percentile, basic, or bca")
    warnings = list(sample_warnings(sample.tolist()))
    if len(sample) < 10:
        warnings.append(
            AnalysisWarning(
                WarningCode.UNSTABLE_INTERVAL,
                "bootstrap limits may be unstable with fewer than 10 observations",
            )
        )
    return ConfidenceInterval(
        estimate,
        float(lower),
        float(upper),
        confidence,
        f"{method}_bootstrap",
        len(sample),
        len(sample),
        seed,
        tuple(warnings),
    )


def paired_bootstrap_interval(
    left: Sequence[float],
    right: Sequence[float],
    *,
    confidence: float = 0.95,
    method: str = "percentile",
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Bootstrap the paired score differences using shared record indices."""

    left_values, right_values = paired_values(left, right, minimum=2)
    differences = np.asarray(right_values, dtype=np.float64) - np.asarray(
        left_values, dtype=np.float64
    )
    interval = bootstrap_interval(
        differences.tolist(),
        confidence=confidence,
        method=method,
        resamples=resamples,
        seed=seed,
    )
    return ConfidenceInterval(
        interval.estimate,
        interval.lower,
        interval.upper,
        interval.confidence,
        f"paired_{interval.method}",
        len(left_values),
        len(left_values),
        seed,
        interval.warnings,
    )


def stratified_bootstrap_interval(
    values: Sequence[float],
    strata: Sequence[str],
    *,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Bootstrap within every observed stratum while preserving stratum sizes."""

    sample = np.asarray(finite_values(values, minimum=2), dtype=np.float64)
    if len(sample) != len(strata):
        raise ValueError("values and strata must have equal lengths")
    _bootstrap_arguments(confidence, resamples, seed)
    positions: dict[str, list[int]] = defaultdict(list)
    for index, stratum in enumerate(strata):
        positions[str(stratum)].append(index)
    generator = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    arrays = [np.asarray(indexes, dtype=np.int64) for indexes in positions.values()]
    for index in range(resamples):
        selected = np.concatenate(
            [generator.choice(indexes, size=len(indexes), replace=True) for indexes in arrays]
        )
        draws[index] = float(np.mean(sample[selected]))
    alpha = 1 - confidence
    lower, upper = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    return ConfidenceInterval(
        float(np.mean(sample)),
        float(lower),
        float(upper),
        confidence,
        "stratified_percentile_bootstrap",
        len(sample),
        len(sample),
        seed,
        sample_warnings(sample.tolist()),
    )


def cluster_bootstrap_interval(
    values: Sequence[float],
    clusters: Sequence[str],
    *,
    confidence: float = 0.95,
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Resample whole clusters to preserve within-cluster dependence."""

    sample = np.asarray(finite_values(values, minimum=2), dtype=np.float64)
    if len(sample) != len(clusters):
        raise ValueError("values and clusters must have equal lengths")
    _bootstrap_arguments(confidence, resamples, seed)
    positions: dict[str, list[int]] = defaultdict(list)
    for index, cluster in enumerate(clusters):
        positions[str(cluster)].append(index)
    cluster_ids = sorted(positions)
    if len(cluster_ids) < 2:
        raise ValueError("cluster bootstrap requires at least two clusters")
    generator = np.random.default_rng(seed)
    draws = np.empty(resamples, dtype=np.float64)
    for index in range(resamples):
        selected_clusters = generator.choice(cluster_ids, size=len(cluster_ids), replace=True)
        selected = [
            position for cluster in selected_clusters for position in positions[str(cluster)]
        ]
        draws[index] = float(np.mean(sample[selected]))
    alpha = 1 - confidence
    lower, upper = np.quantile(draws, [alpha / 2, 1 - alpha / 2])
    warnings = list(sample_warnings(sample.tolist()))
    if len(cluster_ids) < 20:
        warnings.append(
            AnalysisWarning(
                WarningCode.TOO_FEW_CLUSTERS,
                f"only {len(cluster_ids)} clusters are available",
            )
        )
    return ConfidenceInterval(
        float(np.mean(sample)),
        float(lower),
        float(upper),
        confidence,
        "cluster_percentile_bootstrap",
        len(sample),
        len(cluster_ids),
        seed,
        tuple(warnings),
    )


def quantile_bootstrap_interval(
    values: Sequence[float],
    *,
    quantile: float,
    confidence: float = 0.95,
    method: str = "percentile",
    resamples: int = 10_000,
    seed: int = 0,
) -> ConfidenceInterval:
    """Bootstrap an arbitrary quantile, including the median at 0.5."""

    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between zero and one")
    return bootstrap_interval(
        values,
        statistic=lambda sample: float(np.quantile(sample, quantile)),
        confidence=confidence,
        method=method,
        resamples=resamples,
        seed=seed,
    )


def _bca_limits(
    sample: np.ndarray,
    draws: np.ndarray,
    statistic: Statistic,
    estimate: float,
    alpha: float,
) -> tuple[float, float]:
    proportion_less = float(np.mean(draws < estimate))
    epsilon = 1 / (2 * len(draws))
    bias = float(stats.norm.ppf(np.clip(proportion_less, epsilon, 1 - epsilon)))
    jackknife = np.asarray(
        [statistic(np.delete(sample, index)) for index in range(len(sample))],
        dtype=np.float64,
    )
    jackknife_mean = float(np.mean(jackknife))
    numerator = float(np.sum((jackknife_mean - jackknife) ** 3))
    denominator = 6 * float(np.sum((jackknife_mean - jackknife) ** 2)) ** 1.5
    acceleration = numerator / denominator if denominator else 0.0
    probabilities: list[float] = []
    for probability in (alpha / 2, 1 - alpha / 2):
        z = float(stats.norm.ppf(probability))
        adjusted = stats.norm.cdf(bias + (bias + z) / (1 - acceleration * (bias + z)))
        probabilities.append(float(np.clip(adjusted, 0, 1)))
    lower, upper = np.quantile(draws, probabilities)
    return float(min(lower, upper)), float(max(lower, upper))


def _confidence(confidence: float) -> None:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between zero and one")


def _bootstrap_arguments(confidence: float, resamples: int, seed: int) -> None:
    _confidence(confidence)
    if resamples < 200:
        raise ValueError("at least 200 bootstrap resamples are required")
    if not 0 <= seed < (1 << 64):
        raise ValueError("seed must be an unsigned 64-bit integer")


def _mean(sample: np.ndarray) -> float:
    return float(np.mean(sample))
