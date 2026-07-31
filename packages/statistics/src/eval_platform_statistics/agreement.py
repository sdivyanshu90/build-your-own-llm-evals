"""Agreement and ordinal association statistics for judge calibration."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

import numpy as np
from scipy import stats


def weighted_kappa(
    expected: Sequence[int],
    observed: Sequence[int],
    *,
    weighting: str = "quadratic",
) -> float | None:
    """Cohen weighted kappa for an ordered integer scale."""

    if len(expected) != len(observed) or not expected:
        raise ValueError("ratings must be equally sized and non-empty")
    if weighting not in {"linear", "quadratic"}:
        raise ValueError("weighting must be linear or quadratic")
    labels = sorted(set(expected) | set(observed))
    if len(labels) == 1:
        return 1.0
    positions = {label: index for index, label in enumerate(labels)}
    size = len(labels)
    observed_matrix = np.zeros((size, size), dtype=np.float64)
    for left, right in zip(expected, observed, strict=True):
        observed_matrix[positions[left], positions[right]] += 1
    observed_matrix /= len(expected)
    left_marginal = np.sum(observed_matrix, axis=1)
    right_marginal = np.sum(observed_matrix, axis=0)
    expected_matrix = np.outer(left_marginal, right_marginal)
    distances = np.fromfunction(
        lambda left, right: np.abs(left - right) / (size - 1),
        (size, size),
    )
    if weighting == "quadratic":
        distances = distances**2
    observed_disagreement = float(np.sum(distances * observed_matrix))
    expected_disagreement = float(np.sum(distances * expected_matrix))
    if expected_disagreement == 0:
        return 1.0 if observed_disagreement == 0 else None
    return 1 - observed_disagreement / expected_disagreement


def krippendorff_alpha_nominal(ratings: Sequence[Sequence[str | None]]) -> float | None:
    """Krippendorff alpha for nominal labels with missing ratings supported."""

    if not ratings:
        raise ValueError("at least one unit is required")
    observed_disagreements = 0
    observed_pairs = 0
    all_values: list[str] = []
    for unit in ratings:
        values = [value for value in unit if value is not None]
        all_values.extend(values)
        for left_index, left in enumerate(values):
            for right in values[left_index + 1 :]:
                observed_pairs += 1
                observed_disagreements += left != right
    if observed_pairs == 0 or len(all_values) < 2:
        return None
    counts = Counter(all_values)
    total = len(all_values)
    expected_disagreement = 1 - sum(count * (count - 1) for count in counts.values()) / (
        total * (total - 1)
    )
    if expected_disagreement == 0:
        return 1.0 if observed_disagreements == 0 else None
    observed_disagreement = observed_disagreements / observed_pairs
    return 1 - observed_disagreement / expected_disagreement


def rank_correlations(
    expected: Sequence[float],
    observed: Sequence[float],
) -> dict[str, float]:
    """Spearman rho and Kendall tau for ordinal judge scores."""

    if len(expected) != len(observed) or len(expected) < 2:
        raise ValueError("scores must be equally sized with at least two observations")
    spearman = stats.spearmanr(expected, observed)
    kendall = stats.kendalltau(expected, observed)
    return {"spearman_rho": float(spearman.statistic), "kendall_tau": float(kendall.statistic)}
