"""Judge calibration and agreement measures with explicit denominators."""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CategoricalCalibration:
    """Categorical calibration summary."""

    sample_count: int
    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    confusion_matrix: dict[str, dict[str, int]]
    cohen_kappa: float | None


def categorical_calibration(
    expected: Sequence[Hashable],
    observed: Sequence[Hashable],
) -> CategoricalCalibration:
    """Calculate categorical performance and two-rater agreement."""

    if len(expected) != len(observed) or not expected:
        raise ValueError("expected and observed labels must be equally sized and non-empty")
    labels = sorted({str(value) for value in [*expected, *observed]})
    expected_text = [str(value) for value in expected]
    observed_text = [str(value) for value in observed]
    matrix = {
        actual: {
            predicted: sum(
                left == actual and right == predicted
                for left, right in zip(expected_text, observed_text, strict=True)
            )
            for predicted in labels
        }
        for actual in labels
    }
    precision: list[float] = []
    recall: list[float] = []
    f1: list[float] = []
    for label in labels:
        true_positive = matrix[label][label]
        false_positive = sum(matrix[actual][label] for actual in labels if actual != label)
        false_negative = sum(matrix[label][predicted] for predicted in labels if predicted != label)
        label_precision = (
            true_positive / (true_positive + false_positive)
            if true_positive + false_positive
            else 0.0
        )
        label_recall = (
            true_positive / (true_positive + false_negative)
            if true_positive + false_negative
            else 0.0
        )
        precision.append(label_precision)
        recall.append(label_recall)
        f1.append(
            2 * label_precision * label_recall / (label_precision + label_recall)
            if label_precision + label_recall
            else 0.0
        )
    agreement = sum(left == right for left, right in zip(expected_text, observed_text, strict=True))
    expected_counts = Counter(expected_text)
    observed_counts = Counter(observed_text)
    chance = (
        sum(expected_counts[label] * observed_counts[label] for label in labels)
        / len(expected_text) ** 2
    )
    observed_agreement = agreement / len(expected_text)
    kappa = (
        (observed_agreement - chance) / (1 - chance)
        if chance < 1
        else (1.0 if observed_agreement == 1 else None)
    )
    return CategoricalCalibration(
        sample_count=len(expected_text),
        accuracy=observed_agreement,
        macro_precision=sum(precision) / len(labels),
        macro_recall=sum(recall) / len(labels),
        macro_f1=sum(f1) / len(labels),
        confusion_matrix=matrix,
        cohen_kappa=kappa,
    )


def brier_score(outcomes: Sequence[bool], confidences: Sequence[float]) -> float:
    """Mean squared probabilistic error with strict probability bounds."""

    if len(outcomes) != len(confidences) or not outcomes:
        raise ValueError("outcomes and confidences must be equally sized and non-empty")
    if any(not 0 <= confidence <= 1 for confidence in confidences):
        raise ValueError("confidence must be a probability")
    return sum(
        (confidence - float(outcome)) ** 2
        for outcome, confidence in zip(outcomes, confidences, strict=True)
    ) / len(outcomes)
