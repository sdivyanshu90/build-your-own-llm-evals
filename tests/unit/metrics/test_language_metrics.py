"""Language and structured-output metric correctness tests."""

from __future__ import annotations

import math

import pytest
from eval_platform_metrics.base import MetricContext, TaskType
from eval_platform_metrics.language import (
    bleu_score,
    character_error_rate,
    classification_metrics,
    cosine_similarity,
    json_schema_compliance,
    multilabel_metrics,
    safe_regex_match,
    structured_field_accuracy,
    token_precision_recall_f1,
    word_error_rate,
)
from eval_platform_metrics.registry import builtin_registry


def test_token_precision_recall_and_f1_hand_example() -> None:
    result = token_precision_recall_f1("the red red fox", "the red fox jumps")
    assert result == {"precision": 0.75, "recall": 0.75, "f1": 0.75}


def test_empty_token_denominators_are_explicit() -> None:
    assert token_precision_recall_f1("", "") == {
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert token_precision_recall_f1("x", "")["recall"] == 0.0


def test_classification_report_and_confusion_matrix() -> None:
    result = classification_metrics(
        ["cat", "cat", "dog", "dog"],
        ["cat", "dog", "dog", "dog"],
    )
    assert result["accuracy"] == 0.75
    assert result["labels"] == ["cat", "dog"]
    assert result["confusion_matrix"] == [[1, 1], [0, 2]]
    assert result["micro"]["f1"] == 0.75


def test_multilabel_metrics() -> None:
    result = multilabel_metrics(
        [{"a", "b"}, {"b"}],
        [{"a"}, {"b"}],
    )
    assert result["subset_accuracy"] == 0.5
    assert 0 <= result["micro_f1"] <= 1


def test_edit_error_rates_and_bleu_ranges() -> None:
    assert character_error_rate("kitten", "sitten") == pytest.approx(1 / 6)
    assert word_error_rate("one two", "one three") == 0.5
    assert bleu_score("the cat sat", ["the cat sat"]) == pytest.approx(1)


def test_json_schema_and_structured_field_accuracy() -> None:
    schema = {
        "type": "object",
        "properties": {"answer": {"type": "integer"}},
        "required": ["answer"],
        "additionalProperties": False,
    }
    assert json_schema_compliance('{"answer": 42}', schema) == (1.0, [])
    invalid, errors = json_schema_compliance('{"answer":"42"}', schema)
    assert invalid == 0
    assert errors[0]["pointer"] == "/answer"
    fields = structured_field_accuracy(
        {"answer": 42},
        {"answer": 42, "unit": "kg"},
        ["answer", "unit"],
    )
    assert fields["accuracy"] == 0.5
    assert fields["missing_fields"] == ["unit"]


def test_safe_regex_rejects_nested_quantifier() -> None:
    with pytest.raises(ValueError, match="high-risk"):
        safe_regex_match("(a+)+$", "a" * 100)
    assert safe_regex_match(r"^answer:\s+\d+$", "answer: 42")


def test_cosine_similarity_handles_zero_and_known_vectors() -> None:
    assert cosine_similarity([1, 0], [1, 0]) == 1
    assert cosine_similarity([1, 0], [0, 1]) == 0
    assert cosine_similarity([0, 0], [1, 1]) == 0


@pytest.mark.parametrize("identifier", ["language/exact-match", "language/token-f1"])
def test_registry_evaluates_bounded_metrics(identifier: str) -> None:
    result = builtin_registry().evaluate(
        identifier,
        MetricContext(
            task_type=TaskType.QA,
            prediction="Paris",
            reference="Paris",
        ),
    )
    assert result.scalar is not None
    assert math.isfinite(result.scalar)
    assert 0 <= result.scalar <= 1
