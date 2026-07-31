"""Documented approximate power and sample-size planning utilities."""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy import stats


@dataclass(frozen=True, slots=True)
class SampleSizePlan:
    """Approximate design size and the assumptions that produced it."""

    sample_size: int
    alpha: float
    power: float
    effect: float
    method: str
    assumptions: tuple[str, ...]


def paired_continuous_sample_size(
    *,
    standardized_effect: float,
    alpha: float = 0.05,
    power: float = 0.8,
    two_sided: bool = True,
) -> SampleSizePlan:
    """Normal-approximation paired sample size based on difference-score SD."""

    _inputs(standardized_effect, alpha, power)
    alpha_quantile = 1 - alpha / (2 if two_sided else 1)
    n = math.ceil(
        ((stats.norm.ppf(alpha_quantile) + stats.norm.ppf(power)) / abs(standardized_effect)) ** 2
    )
    return SampleSizePlan(
        max(2, n),
        alpha,
        power,
        standardized_effect,
        "normal_approximation_paired_continuous",
        (
            "effect is mean paired difference divided by its standard deviation",
            "difference observations are independent across records",
            "normal approximation; inflate for attrition and non-normality",
        ),
    )


def paired_preference_sample_size(
    *,
    win_probability: float,
    alpha: float = 0.05,
    power: float = 0.8,
    tie_rate: float = 0,
) -> SampleSizePlan:
    """Approximate total pairs for a sign test, inflating for anticipated ties."""

    if not 0 < win_probability < 1 or win_probability == 0.5:
        raise ValueError("win probability must be in (0, 1) and differ from 0.5")
    if not 0 <= tie_rate < 1:
        raise ValueError("tie rate must be between zero and one")
    _inputs(win_probability - 0.5, alpha, power)
    null_variance = 0.25
    alternative_variance = win_probability * (1 - win_probability)
    decisive = math.ceil(
        (
            stats.norm.ppf(1 - alpha / 2) * math.sqrt(null_variance)
            + stats.norm.ppf(power) * math.sqrt(alternative_variance)
        )
        ** 2
        / (win_probability - 0.5) ** 2
    )
    total = math.ceil(decisive / (1 - tie_rate))
    return SampleSizePlan(
        total,
        alpha,
        power,
        win_probability - 0.5,
        "normal_approximation_pairwise_sign",
        (
            "decisive outcomes are independent",
            f"anticipated tie rate is {tie_rate:.3f}",
            "normal approximation; validate small designs with exact power",
        ),
    )


def minimum_detectable_standardized_effect(
    *,
    sample_size: int,
    alpha: float = 0.05,
    power: float = 0.8,
) -> float:
    """Approximate two-sided paired standardized effect detectable at target power."""

    if sample_size < 2:
        raise ValueError("sample size must be at least two")
    _inputs(1.0, alpha, power)
    return float((stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(power)) / math.sqrt(sample_size))


def _inputs(effect: float, alpha: float, power: float) -> None:
    if effect == 0 or not math.isfinite(effect):
        raise ValueError("effect must be finite and non-zero")
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must be between zero and 0.5")
    if not 0.5 < power < 1:
        raise ValueError("power must be between 0.5 and one")
