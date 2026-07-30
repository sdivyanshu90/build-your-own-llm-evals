"""Language-model lexical, classification, structured, and semantic metrics."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
import sacrebleu
from jsonschema import Draft202012Validator
from rouge_score import rouge_scorer
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)

from eval_platform_metrics.base import (
    EMPTY_CONFIG_SCHEMA,
    RESULT_SCHEMA,
    Determinism,
    FailureBehavior,
    MetricContext,
    MetricDefinition,
    MetricResult,
    ScoreDirection,
    TaskType,
)


def normalize_text(value: str) -> str:
    """NFC-normalize, case-fold, and collapse Unicode whitespace."""

    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def _tokens(value: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", normalize_text(value), flags=re.UNICODE)


def token_precision_recall_f1(prediction: str, reference: str) -> dict[str, float]:
    """Bag-of-token precision, recall, and F1 with explicit empty behavior."""

    predicted = Counter(_tokens(prediction))
    expected = Counter(_tokens(reference))
    overlap = sum((predicted & expected).values())
    predicted_count = sum(predicted.values())
    expected_count = sum(expected.values())
    precision = overlap / predicted_count if predicted_count else float(not expected_count)
    recall = overlap / expected_count if expected_count else float(not predicted_count)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


@dataclass(frozen=True, slots=True)
class MatchMetric:
    """Exact-match family configured by normalization mode."""

    identifier: str
    name: str
    mode: str

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier=self.identifier,
            name=self.name,
            version="1.0.0",
            description=f"String match using {self.mode} comparison.",
            task_types=frozenset(TaskType),
            required_fields=frozenset({"prediction", "reference"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=True,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(n)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        prediction = str(context.prediction)
        reference = str(context.reference)
        if self.mode == "normalized":
            prediction, reference = normalize_text(prediction), normalize_text(reference)
        elif self.mode == "case_insensitive":
            prediction, reference = prediction.casefold(), reference.casefold()
        score = float(prediction == reference)
        return MetricResult(self.identifier, "1.0.0", scalar=score)


class TokenF1Metric:
    """Token-level overlap with all components in structured output."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/token-f1",
            name="Token F1",
            version="1.0.0",
            description="Bag-of-token precision, recall, and harmonic mean.",
            task_types=frozenset(TaskType),
            required_fields=frozenset({"prediction", "reference"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=True,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(n)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        values = token_precision_recall_f1(
            str(context.prediction),
            str(context.reference),
        )
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=values["f1"],
            structured=values,
        )


def classification_metrics(
    expected: Sequence[str],
    predicted: Sequence[str],
    *,
    labels: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return accuracy, all requested averaging modes, and confusion matrix."""

    if len(expected) != len(predicted) or not expected:
        raise ValueError("classification arrays must be non-empty and equal length")
    ordered_labels = list(labels or sorted(set(expected) | set(predicted)))
    result: dict[str, Any] = {
        "accuracy": float(accuracy_score(expected, predicted)),
        "labels": ordered_labels,
        "confusion_matrix": confusion_matrix(
            expected,
            predicted,
            labels=ordered_labels,
        ).tolist(),
    }
    for average in ("macro", "micro", "weighted"):
        precision, recall, f1, _ = precision_recall_fscore_support(
            expected,
            predicted,
            labels=ordered_labels,
            average=average,
            zero_division=0,
        )
        result[average] = {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
        }
    return result


def multilabel_metrics(
    expected: Sequence[set[str]],
    predicted: Sequence[set[str]],
) -> dict[str, float]:
    """Return subset accuracy and micro/macro label PRF."""

    if len(expected) != len(predicted) or not expected:
        raise ValueError("multilabel arrays must be non-empty and equal length")
    labels = sorted(set().union(*expected, *predicted))
    subset_accuracy = sum(left == right for left, right in zip(expected, predicted, strict=True))
    if not labels:
        return {
            "subset_accuracy": 1.0,
            "micro_precision": 1.0,
            "micro_recall": 1.0,
            "micro_f1": 1.0,
            "macro_f1": 1.0,
        }
    expected_matrix = [[label in row for label in labels] for row in expected]
    predicted_matrix = [[label in row for label in labels] for row in predicted]
    micro = precision_recall_fscore_support(
        expected_matrix,
        predicted_matrix,
        average="micro",
        zero_division=0,
    )
    macro = precision_recall_fscore_support(
        expected_matrix,
        predicted_matrix,
        average="macro",
        zero_division=0,
    )
    return {
        "subset_accuracy": subset_accuracy / len(expected),
        "micro_precision": float(micro[0]),
        "micro_recall": float(micro[1]),
        "micro_f1": float(micro[2]),
        "macro_f1": float(macro[2]),
    }


def rouge_scores(prediction: str, reference: str) -> dict[str, float]:
    """Return ROUGE-1, ROUGE-2, and ROUGE-Lsum F1 scores."""

    scorer = rouge_scorer.RougeScorer(
        ["rouge1", "rouge2", "rougeLsum"],
        use_stemmer=False,
    )
    scores = scorer.score(reference, prediction)
    return {identifier: float(value.fmeasure) for identifier, value in scores.items()}


def bleu_score(prediction: str, references: Sequence[str]) -> float:
    """Return sentence BLEU in [0, 1] using explicit exponential smoothing."""

    if not references:
        raise ValueError("BLEU requires at least one reference")
    value = float(
        sacrebleu.sentence_bleu(
            prediction,
            list(references),
            smooth_method="exp",
            use_effective_order=True,
        ).score
        / 100
    )
    return min(1.0, max(0.0, value))


def edit_distance(left: Sequence[Any], right: Sequence[Any]) -> int:
    """Compute Levenshtein distance in O(min(n,m)) memory."""

    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_value in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_value in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + (left_value != right_value),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(prediction: str, reference: str) -> float:
    """Character errors divided by reference character count."""

    if not reference:
        return 0.0 if not prediction else 1.0
    return edit_distance(list(prediction), list(reference)) / len(reference)


def word_error_rate(prediction: str, reference: str) -> float:
    """Word errors divided by reference word count."""

    predicted = prediction.split()
    expected = reference.split()
    if not expected:
        return 0.0 if not predicted else 1.0
    return edit_distance(predicted, expected) / len(expected)


def json_validity(prediction: str) -> tuple[float, Any | None, str | None]:
    """Parse JSON while rejecting duplicate object keys."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate key: {key}")
            result[key] = value
        return result

    try:
        return 1.0, json.loads(prediction, object_pairs_hook=reject_duplicates), None
    except (json.JSONDecodeError, ValueError) as error:
        return 0.0, None, str(error)


def json_schema_compliance(
    prediction: str,
    schema: Mapping[str, Any],
) -> tuple[float, list[dict[str, str]]]:
    """Validate parsed JSON and return bounded public error evidence."""

    valid, value, parse_error = json_validity(prediction)
    if not valid:
        return 0.0, [{"pointer": "/", "message": parse_error or "invalid JSON"}]
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    return (
        float(not errors),
        [
            {
                "pointer": "/" + "/".join(str(part) for part in error.absolute_path),
                "message": error.message,
            }
            for error in errors[:100]
        ],
    )


def structured_field_accuracy(
    prediction: Mapping[str, Any],
    reference: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    """Compare explicit top-level structured fields without hiding missing values."""

    results: dict[str, bool] = {}
    missing: list[str] = []
    for field in fields:
        if field not in prediction or field not in reference:
            missing.append(field)
            continue
        results[field] = prediction[field] == reference[field]
    denominator = len(fields)
    score = sum(results.values()) / denominator if denominator else 1.0
    return {"accuracy": score, "fields": results, "missing_fields": missing}


_UNSAFE_REGEX = re.compile(
    r"\\[1-9]|\(\?<[=!]|(?:\*|\+|\})\s*(?:\*|\+|\{)|\([^)]*[*+{][^)]*\)[*+{]"
)


def safe_regex_match(pattern: str, prediction: str, *, full_match: bool = False) -> bool:
    """Evaluate a deliberately restricted rule pattern."""

    if len(pattern) > 500 or _UNSAFE_REGEX.search(pattern):
        raise ValueError("pattern uses a disallowed high-risk regex construct")
    compiled = re.compile(pattern)
    return bool(compiled.fullmatch(prediction) if full_match else compiled.search(prediction))


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Cosine similarity with explicit zero-vector behavior."""

    if len(left) != len(right) or not left:
        raise ValueError("embedding vectors must have the same nonzero dimension")
    left_array = np.asarray(left, dtype=float)
    right_array = np.asarray(right, dtype=float)
    denominator = float(np.linalg.norm(left_array) * np.linalg.norm(right_array))
    return float(np.dot(left_array, right_array) / denominator) if denominator else 0.0


class SafetyClassifier(Protocol):
    """External toxicity/safety classifier boundary."""

    @property
    def identifier(self) -> str:
        """Return the versioned classifier identity."""

        raise TypeError("protocol declaration has no runtime implementation")

    def classify(self, text: str) -> dict[str, float]:
        """Return label probabilities without hidden global configuration."""

        raise TypeError("protocol declaration has no runtime implementation")


class JsonValidityMetric:
    """Built-in JSON validity metric."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/json-validity",
            name="JSON validity",
            version="1.0.0",
            description="Parses one JSON value and rejects duplicate object keys.",
            task_types=frozenset({TaskType.GENERATION, TaskType.EXTRACTION}),
            required_fields=frozenset({"prediction"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(n)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        score, _, error = json_validity(str(context.prediction))
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=score,
            explanation=error,
        )


@dataclass(frozen=True, slots=True)
class TextOverlapMetric:
    """ROUGE, BLEU, edit-distance, CER, and WER per-sample metric."""

    kind: str

    @property
    def definition(self) -> MetricDefinition:
        lower_better = self.kind in {"edit-distance", "cer", "wer"}
        return MetricDefinition(
            identifier=f"language/{self.kind}",
            name=self.kind.replace("-", " ").upper(),
            version="1.0.0",
            description=f"Deterministic {self.kind} text comparison.",
            task_types=frozenset(
                {
                    TaskType.GENERATION,
                    TaskType.QA,
                    TaskType.SUMMARIZATION,
                    TaskType.CONVERSATION,
                }
            ),
            required_fields=frozenset({"prediction", "reference"}),
            output_schema=RESULT_SCHEMA,
            direction=(
                ScoreDirection.LOWER_IS_BETTER if lower_better else ScoreDirection.HIGHER_IS_BETTER
            ),
            minimum=0,
            maximum=None if lower_better else 1,
            reference_required=True,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(n*m) worst case for edit metrics; linear scoring otherwise",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        prediction = str(context.prediction)
        reference = str(context.reference)
        structured: dict[str, Any] | None = None
        if self.kind.startswith("rouge"):
            scores = rouge_scores(prediction, reference)
            key = {"rouge-1": "rouge1", "rouge-2": "rouge2", "rouge-l": "rougeLsum"}[self.kind]
            value = scores[key]
            structured = scores
        elif self.kind == "bleu":
            value = bleu_score(prediction, [reference])
        elif self.kind == "cer":
            value = character_error_rate(prediction, reference)
        elif self.kind == "wer":
            value = word_error_rate(prediction, reference)
        else:
            value = float(edit_distance(prediction, reference))
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=value,
            structured=structured,
        )


class ClassificationAccuracyMetric:
    """Per-sample categorical correctness; aggregate PRF is computed over the cohort."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/classification-accuracy",
            name="Classification accuracy",
            version="1.0.0",
            description="One when the predicted label equals the reference label.",
            task_types=frozenset({TaskType.CLASSIFICATION}),
            required_fields=frozenset({"prediction", "reference"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=True,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="classification_report",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema=EMPTY_CONFIG_SCHEMA,
            computational_cost="O(1)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        predicted = str(context.prediction).strip()
        expected = str(context.reference).strip()
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=float(predicted == expected),
            label=predicted,
            metadata={"reference_label": expected},
        )


class JsonSchemaMetric:
    """JSON Schema compliance metric with bounded error evidence."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/json-schema-compliance",
            name="JSON Schema compliance",
            version="1.0.0",
            description="Valid JSON satisfying the configured Draft 2020-12 schema.",
            task_types=frozenset({TaskType.GENERATION, TaskType.EXTRACTION}),
            required_fields=frozenset({"prediction"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"schema": {"type": "object"}},
                "required": ["schema"],
            },
            computational_cost="O(document + schema)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {}
        score, errors = json_schema_compliance(
            str(context.prediction),
            config["schema"],
        )
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=score,
            structured={"errors": errors},
        )


class RegexMetric:
    """Restricted regex/rule criterion."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/regex-match",
            name="Restricted regex match",
            version="1.0.0",
            description="Searches output with a restricted bounded-size regular expression.",
            task_types=frozenset(TaskType),
            required_fields=frozenset({"prediction"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "pattern": {"type": "string", "minLength": 1, "maxLength": 500},
                    "full_match": {"type": "boolean"},
                },
                "required": ["pattern"],
            },
            computational_cost="bounded regex evaluation",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {}
        matched = safe_regex_match(
            str(config["pattern"]),
            str(context.prediction),
            full_match=bool(config.get("full_match", False)),
        )
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=float(matched),
        )


class SemanticSimilarityMetric:
    """Cosine similarity over precomputed versioned embeddings."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="language/semantic-similarity",
            name="Semantic similarity",
            version="1.0.0",
            description="Cosine similarity of supplied prediction/reference embeddings.",
            task_types=frozenset(TaskType),
            required_fields=frozenset({"prediction", "reference"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=-1,
            maximum=1,
            reference_required=True,
            external_model_required=True,
            determinism=Determinism.EXTERNAL_MODEL,
            aggregation="mean",
            failure_behavior=FailureBehavior.RECORD_FAILURE,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prediction_embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 1,
                    },
                    "reference_embedding": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 1,
                    },
                    "embedding_model": {"type": "string", "minLength": 1},
                },
                "required": [
                    "prediction_embedding",
                    "reference_embedding",
                    "embedding_model",
                ],
            },
            computational_cost="O(embedding dimensions) plus external embedding calls",
            monetary_cost="provider-dependent",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del context
        config = configuration or {}
        score = cosine_similarity(
            config["prediction_embedding"],
            config["reference_embedding"],
        )
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=score,
            metadata={"embedding_model": config["embedding_model"]},
        )


def refusal_rate(labels: Sequence[str]) -> float:
    """Return refusal count divided by all classified outputs."""

    return sum(label == "refusal" for label in labels) / len(labels) if labels else math.nan
