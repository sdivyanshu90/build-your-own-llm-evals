"""Judge drift, sensitivity, and disagreement diagnostics."""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from eval_platform_evaluators.judge import JudgeResponse


@dataclass(frozen=True, slots=True)
class JudgeDrift:
    """Window comparison suitable for alerting, not a causal claim."""

    baseline_count: int
    current_count: int
    verdict_total_variation: float
    mean_score_shifts: dict[str, float]
    confidence_shift: float
    alert: bool


def judge_drift(
    baseline: Sequence[JudgeResponse],
    current: Sequence[JudgeResponse],
    *,
    verdict_threshold: float = 0.15,
    score_threshold: float = 0.5,
) -> JudgeDrift:
    """Compare judge output distributions between calibration windows."""

    if not baseline or not current:
        raise ValueError("both drift windows must be non-empty")
    if verdict_threshold < 0 or score_threshold < 0:
        raise ValueError("drift thresholds cannot be negative")
    dimensions = set(baseline[0].scores)
    if any(set(response.scores) != dimensions for response in [*baseline, *current]):
        raise ValueError("drift windows must use the same rubric dimensions")
    baseline_counts = Counter(response.verdict for response in baseline)
    current_counts = Counter(response.verdict for response in current)
    labels = set(baseline_counts) | set(current_counts)
    total_variation = 0.5 * sum(
        abs(baseline_counts[label] / len(baseline) - current_counts[label] / len(current))
        for label in labels
    )
    shifts = {
        dimension: statistics.fmean(response.scores[dimension] for response in current)
        - statistics.fmean(response.scores[dimension] for response in baseline)
        for dimension in sorted(dimensions)
    }
    confidence_shift = statistics.fmean(
        response.confidence for response in current
    ) - statistics.fmean(response.confidence for response in baseline)
    return JudgeDrift(
        len(baseline),
        len(current),
        total_variation,
        shifts,
        confidence_shift,
        total_variation > verdict_threshold
        or any(abs(shift) > score_threshold for shift in shifts.values()),
    )


def ensemble_disagreement(
    responses_by_judge: dict[str, Sequence[JudgeResponse]],
) -> dict[str, float | int]:
    """Report pairwise verdict disagreement across a judge ensemble."""

    if len(responses_by_judge) < 2:
        raise ValueError("an ensemble requires at least two judges")
    lengths = {len(responses) for responses in responses_by_judge.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError("judge response vectors must be equally sized and non-empty")
    judges = sorted(responses_by_judge)
    disagreements = comparisons = 0
    for position in range(next(iter(lengths))):
        for left_index, left in enumerate(judges):
            for right in judges[left_index + 1 :]:
                comparisons += 1
                disagreements += (
                    responses_by_judge[left][position].verdict
                    != responses_by_judge[right][position].verdict
                )
    return {
        "judge_count": len(judges),
        "sample_count": next(iter(lengths)),
        "pairwise_comparisons": comparisons,
        "disagreement_rate": disagreements / comparisons,
    }
