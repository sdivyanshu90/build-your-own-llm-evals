"""Typed statistical results, warnings, and explicit paired-data alignment."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class WarningCode(StrEnum):
    """Stable machine-readable statistical warning taxonomy."""

    VERY_SMALL_SAMPLE = "very_small_sample"
    ZERO_VARIANCE = "zero_variance"
    DEGENERATE_OUTCOME = "degenerate_outcome"
    ALL_TIES = "all_ties"
    EXTREME_IMBALANCE = "extreme_class_imbalance"
    EXCESSIVE_MISSINGNESS = "excessive_missingness"
    TOO_FEW_CLUSTERS = "too_few_clusters"
    UNSTABLE_INTERVAL = "unstable_confidence_interval"
    ASSUMPTION_VIOLATION = "assumption_violation"
    EXCESSIVE_DISAGREEMENT = "excessive_judge_disagreement"


@dataclass(frozen=True, slots=True)
class AnalysisWarning:
    """A warning that must travel with the numerical result."""

    code: WarningCode
    message: str


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    """Estimate and confidence limits with complete analysis provenance."""

    estimate: float
    lower: float
    upper: float
    confidence: float
    method: str
    sample_size: int
    effective_sample_size: int
    seed: int | None = None
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        if not 0 < self.confidence < 1:
            raise ValueError("confidence must be strictly between zero and one")
        if self.sample_size < 0 or self.effective_sample_size < 0:
            raise ValueError("sample sizes cannot be negative")
        if self.lower > self.upper:
            raise ValueError("confidence interval lower bound exceeds upper bound")


@dataclass(frozen=True, slots=True)
class HypothesisTest:
    """Inferential result that never hides its effective denominator."""

    statistic: float
    p_value: float
    method: str
    alternative: str
    sample_size: int
    effective_sample_size: int
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.p_value <= 1:
            raise ValueError("p-value must be between zero and one")


@dataclass(frozen=True, slots=True)
class PairedSample:
    """Aligned finite values and an explicit account of missing records."""

    record_ids: tuple[str, ...]
    left: tuple[float, ...]
    right: tuple[float, ...]
    union_size: int
    missing_left: int
    missing_right: int
    non_finite: int
    warnings: tuple[AnalysisWarning, ...]

    @property
    def effective_sample_size(self) -> int:
        return len(self.record_ids)

    @property
    def differences(self) -> tuple[float, ...]:
        return tuple(right - left for left, right in zip(self.left, self.right, strict=True))


def align_pairs(
    left: Mapping[str, float | None],
    right: Mapping[str, float | None],
    *,
    excessive_missingness_threshold: float = 0.2,
) -> PairedSample:
    """Align by record identity and report every exclusion.

    Missing and non-finite observations are excluded from numerical procedures,
    but their counts and a warning remain part of the returned object.
    """

    if not 0 <= excessive_missingness_threshold <= 1:
        raise ValueError("missingness threshold must be between zero and one")
    record_ids: list[str] = []
    left_values: list[float] = []
    right_values: list[float] = []
    missing_left = 0
    missing_right = 0
    non_finite = 0
    union = sorted(set(left) | set(right))
    for record_id in union:
        left_value = left.get(record_id)
        right_value = right.get(record_id)
        if left_value is None:
            missing_left += 1
        if right_value is None:
            missing_right += 1
        if left_value is None or right_value is None:
            continue
        if not math.isfinite(left_value) or not math.isfinite(right_value):
            non_finite += 1
            continue
        record_ids.append(record_id)
        left_values.append(float(left_value))
        right_values.append(float(right_value))
    excluded = len(union) - len(record_ids)
    warnings = list(sample_warnings(left_values))
    if union and excluded / len(union) > excessive_missingness_threshold:
        warnings.append(
            AnalysisWarning(
                WarningCode.EXCESSIVE_MISSINGNESS,
                f"{excluded} of {len(union)} records were excluded from paired analysis",
            )
        )
    return PairedSample(
        record_ids=tuple(record_ids),
        left=tuple(left_values),
        right=tuple(right_values),
        union_size=len(union),
        missing_left=missing_left,
        missing_right=missing_right,
        non_finite=non_finite,
        warnings=tuple(warnings),
    )


def finite_values(values: Sequence[float], *, minimum: int = 1) -> tuple[float, ...]:
    """Validate rather than silently discard non-finite observations."""

    converted = tuple(float(value) for value in values)
    if len(converted) < minimum:
        raise ValueError(f"at least {minimum} observations are required")
    if any(not math.isfinite(value) for value in converted):
        raise ValueError("observations must be finite; align or impute missing data explicitly")
    return converted


def paired_values(
    left: Sequence[float],
    right: Sequence[float],
    *,
    minimum: int = 1,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Validate equal-length finite paired vectors."""

    if len(left) != len(right):
        raise ValueError("paired observations must have equal lengths")
    return finite_values(left, minimum=minimum), finite_values(right, minimum=minimum)


def sample_warnings(values: Sequence[float]) -> tuple[AnalysisWarning, ...]:
    """Create standard warnings for small or degenerate numerical samples."""

    warnings: list[AnalysisWarning] = []
    if len(values) < 30:
        warnings.append(
            AnalysisWarning(
                WarningCode.VERY_SMALL_SAMPLE,
                f"only {len(values)} observations are available",
            )
        )
    if len(values) > 1 and max(values) == min(values):
        warnings.append(
            AnalysisWarning(WarningCode.ZERO_VARIANCE, "all observations are identical")
        )
    return tuple(warnings)
