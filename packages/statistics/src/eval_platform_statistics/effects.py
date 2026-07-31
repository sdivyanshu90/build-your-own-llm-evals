"""Effect sizes for paired continuous, binary, and preference outcomes."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from eval_platform_statistics.models import paired_values


@dataclass(frozen=True, slots=True)
class PairedContinuousEffects:
    """Continuous paired effects, oriented as candidate minus baseline."""

    mean_difference: float
    median_difference: float
    relative_improvement: float | None
    standardized_mean_difference_dz: float | None
    probability_of_superiority: float
    sample_size: int


def paired_continuous_effects(
    baseline: Sequence[float],
    candidate: Sequence[float],
) -> PairedContinuousEffects:
    """Calculate paired effects without pretending paired samples are independent."""

    left, right = paired_values(baseline, candidate, minimum=1)
    differences = [
        candidate_value - baseline_value
        for baseline_value, candidate_value in zip(left, right, strict=True)
    ]
    mean_difference = statistics.fmean(differences)
    baseline_mean = statistics.fmean(left)
    relative = mean_difference / abs(baseline_mean) if baseline_mean != 0 else None
    standard_deviation = statistics.stdev(differences) if len(differences) > 1 else 0.0
    standardized = mean_difference / standard_deviation if standard_deviation else None
    wins = sum(value > 0 for value in differences)
    ties = sum(value == 0 for value in differences)
    return PairedContinuousEffects(
        mean_difference=mean_difference,
        median_difference=float(statistics.median(differences)),
        relative_improvement=relative,
        standardized_mean_difference_dz=standardized,
        probability_of_superiority=(wins + 0.5 * ties) / len(differences),
        sample_size=len(differences),
    )


@dataclass(frozen=True, slots=True)
class PairedBinaryEffects:
    """Paired binary risk and discordant-pair odds effects."""

    baseline_rate: float
    candidate_rate: float
    absolute_risk_difference: float
    relative_risk: float | None
    matched_odds_ratio: float | None
    discordant_baseline_only: int
    discordant_candidate_only: int
    sample_size: int


def paired_binary_effects(
    baseline: Sequence[bool],
    candidate: Sequence[bool],
) -> PairedBinaryEffects:
    """Calculate paired binary effects; odds use only discordant pairs."""

    if len(baseline) != len(candidate) or not baseline:
        raise ValueError("paired binary outcomes must be equally sized and non-empty")
    baseline_rate = sum(baseline) / len(baseline)
    candidate_rate = sum(candidate) / len(candidate)
    baseline_only = sum(left and not right for left, right in zip(baseline, candidate, strict=True))
    candidate_only = sum(
        right and not left for left, right in zip(baseline, candidate, strict=True)
    )
    if baseline_only == 0 and candidate_only == 0:
        odds_ratio = None
    elif baseline_only == 0:
        odds_ratio = math.inf
    else:
        odds_ratio = candidate_only / baseline_only
    return PairedBinaryEffects(
        baseline_rate,
        candidate_rate,
        candidate_rate - baseline_rate,
        candidate_rate / baseline_rate if baseline_rate else None,
        odds_ratio,
        baseline_only,
        candidate_only,
        len(baseline),
    )


def tie_adjusted_win_rate(wins: int, losses: int, ties: int) -> float:
    """Preference probability where each explicit tie contributes one half."""

    if min(wins, losses, ties) < 0 or wins + losses + ties == 0:
        raise ValueError("counts must be non-negative and not all zero")
    return (wins + 0.5 * ties) / (wins + losses + ties)
