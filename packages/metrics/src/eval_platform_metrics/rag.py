"""Retrieval and grounded-generation metrics with explicit denominators."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from eval_platform_metrics.base import (
    RESULT_SCHEMA,
    Determinism,
    FailureBehavior,
    MetricContext,
    MetricDefinition,
    MetricResult,
    ScoreDirection,
    TaskType,
)


def _top(retrieved_ids: Sequence[str], k: int) -> Sequence[str]:
    if k < 1:
        raise ValueError("k must be positive")
    return retrieved_ids[:k]


def precision_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | frozenset[str],
    k: int,
) -> float:
    """Relevant retrieved divided by observed retrieved count up to K.

    Empty retrieval returns 0. This platform uses the observed denominator
    ``min(K, retrieved_count)`` rather than assuming missing ranks are irrelevant.
    """

    candidates = _top(retrieved_ids, k)
    return (
        sum(identifier in relevant_ids for identifier in candidates) / len(candidates)
        if candidates
        else 0.0
    )


def recall_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | frozenset[str],
    k: int,
) -> float | None:
    """Unique relevant IDs retrieved divided by all labeled relevant IDs.

    No labeled relevant documents produces ``None`` rather than an invented zero
    or one.
    """

    if not relevant_ids:
        return None
    return len(set(_top(retrieved_ids, k)) & relevant_ids) / len(relevant_ids)


def hit_rate_at_k(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | frozenset[str],
    k: int,
) -> float | None:
    """One when at least one relevant item is retrieved; missing if none are labeled."""

    if not relevant_ids:
        return None
    return float(bool(set(_top(retrieved_ids, k)) & relevant_ids))


def reciprocal_rank(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | frozenset[str],
    k: int | None = None,
) -> float | None:
    """Reciprocal rank of the first relevant item."""

    if not relevant_ids:
        return None
    candidates = retrieved_ids if k is None else _top(retrieved_ids, k)
    for rank, identifier in enumerate(candidates, start=1):
        if identifier in relevant_ids:
            return 1 / rank
    return 0.0


def average_precision(
    retrieved_ids: Sequence[str],
    relevant_ids: set[str] | frozenset[str],
    k: int | None = None,
) -> float | None:
    """Sum precision at each first relevant hit divided by all relevant labels."""

    if not relevant_ids:
        return None
    candidates = retrieved_ids if k is None else _top(retrieved_ids, k)
    seen: set[str] = set()
    score = 0.0
    hits = 0
    for rank, identifier in enumerate(candidates, start=1):
        if identifier in relevant_ids and identifier not in seen:
            hits += 1
            score += hits / rank
            seen.add(identifier)
    return score / len(relevant_ids)


def ndcg(
    retrieved_ids: Sequence[str],
    relevance: Mapping[str, float],
    k: int,
) -> float | None:
    """Normalized discounted cumulative gain using ``2^gain - 1``."""

    if k < 1:
        raise ValueError("k must be positive")
    positive = [max(0.0, float(gain)) for gain in relevance.values()]
    ideal_gains = sorted(positive, reverse=True)[:k]
    ideal = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal_gains, 1))
    if ideal == 0:
        return None
    actual = 0.0
    seen: set[str] = set()
    for rank, identifier in enumerate(retrieved_ids[:k], 1):
        gain = 0.0 if identifier in seen else max(0.0, float(relevance.get(identifier, 0)))
        actual += (2**gain - 1) / math.log2(rank + 1)
        seen.add(identifier)
    return min(1.0, max(0.0, actual / ideal))


def retrieval_coverage(
    retrieved_ids: Sequence[str],
    expected_source_ids: set[str] | frozenset[str],
) -> float | None:
    """Unique expected sources observed divided by all expected sources."""

    if not expected_source_ids:
        return None
    return len(set(retrieved_ids) & expected_source_ids) / len(expected_source_ids)


def duplicate_document_rate(retrieved_ids: Sequence[str]) -> float:
    """Repeated ranks divided by retrieved ranks; empty retrieval is zero."""

    if not retrieved_ids:
        return 0.0
    return (len(retrieved_ids) - len(set(retrieved_ids))) / len(retrieved_ids)


def context_utilization(
    retrieved_ids: Sequence[str],
    used_ids: set[str] | frozenset[str],
) -> float | None:
    """Unique retrieved contexts used by the answer divided by unique retrievals."""

    denominator = set(retrieved_ids)
    return len(denominator & used_ids) / len(denominator) if denominator else None


@dataclass(frozen=True, slots=True)
class EvidenceJudgment:
    """Auditable model-based RAG judgment without hidden reasoning."""

    score: float
    evidence_ids: tuple[str, ...]
    justification: str
    confidence: float

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 1 or not 0 <= self.confidence <= 1:
            raise ValueError("judge score and confidence must be in [0, 1]")
        if not self.justification.strip():
            raise ValueError("judge justification must not be empty")


def claim_support_rates(judgments: Sequence[EvidenceJudgment]) -> dict[str, float | None]:
    """Aggregate claim support judgments for groundedness reporting."""

    if not judgments:
        return {"faithfulness": None, "unsupported_claim_rate": None}
    faithfulness = sum(judgment.score for judgment in judgments) / len(judgments)
    unsupported = sum(judgment.score == 0 for judgment in judgments) / len(judgments)
    return {"faithfulness": faithfulness, "unsupported_claim_rate": unsupported}


_CITATION = re.compile(r"\[source:([A-Za-z0-9._:/-]{1,200})\]")


def extract_citations(answer: str) -> tuple[str, ...]:
    """Extract explicit ``[source:ID]`` citations in display order."""

    return tuple(_CITATION.findall(answer))


def citation_metrics(
    answer: str,
    available_source_ids: set[str] | frozenset[str],
    required_claim_source_ids: set[str] | frozenset[str] = frozenset(),
) -> dict[str, float | None]:
    """Return presence, validity, correctness proxy, and completeness.

    Validity checks whether cited IDs exist. Correctness is the fraction of cited
    IDs that are both available and required for labeled claims. When claim-level
    labels are absent, correctness and completeness are missing rather than
    inferred from citation presence.
    """

    citations = extract_citations(answer)
    unique = set(citations)
    presence = float(bool(citations))
    validity = (
        sum(identifier in available_source_ids for identifier in citations) / len(citations)
        if citations
        else 0.0
    )
    if not required_claim_source_ids:
        correctness = None
        completeness = None
    else:
        correctness = (
            len(unique & available_source_ids & required_claim_source_ids) / len(unique)
            if unique
            else 0.0
        )
        completeness = len(unique & required_claim_source_ids) / len(required_claim_source_ids)
    return {
        "presence": presence,
        "validity": validity,
        "correctness": correctness,
        "completeness": completeness,
    }


class RecallAtKMetric:
    """Registered retrieval recall metric."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="rag/recall-at-k",
            name="Retrieval recall at K",
            version="1.0.0",
            description="Unique labeled relevant items retrieved in the first K ranks.",
            task_types=frozenset({TaskType.RAG}),
            required_fields=frozenset({"retrieved_items"}),
            output_schema=RESULT_SCHEMA,
            direction=ScoreDirection.HIGHER_IS_BETTER,
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean_available",
            failure_behavior=FailureBehavior.RETURN_MISSING,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {"k": {"type": "integer", "minimum": 1, "maximum": 1000}},
                "required": ["k"],
            },
            computational_cost="O(K)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {"k": 10}
        identifiers = [str(item["id"]) for item in context.retrieved_items]
        value = recall_at_k(identifiers, context.relevant_item_ids, int(config["k"]))
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=value,
            missing=value is None,
            explanation=(
                "No relevant-item labels were supplied; recall is undefined."
                if value is None
                else None
            ),
            metadata={
                "k": int(config["k"]),
                "relevant_count": len(context.relevant_item_ids),
                "retrieved_count": len(identifiers),
            },
        )


class PrecisionAtKMetric:
    """Registered observed-denominator retrieval precision."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="rag/precision-at-k",
            name="Retrieval precision at K",
            version="1.0.0",
            description="Relevant ranks divided by observed ranks up to K.",
            task_types=frozenset({TaskType.RAG}),
            required_fields=frozenset({"retrieved_items"}),
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
                "properties": {"k": {"type": "integer", "minimum": 1, "maximum": 1000}},
                "required": ["k"],
            },
            computational_cost="O(K)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {"k": 10}
        identifiers = [str(item["id"]) for item in context.retrieved_items]
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=precision_at_k(
                identifiers,
                context.relevant_item_ids,
                int(config["k"]),
            ),
            metadata={
                "k": int(config["k"]),
                "denominator": min(int(config["k"]), len(identifiers)),
            },
        )


@dataclass(frozen=True, slots=True)
class RetrievalRankingMetric:
    """Hit rate, reciprocal rank, MAP, nDCG, coverage, or duplicate rate."""

    kind: str

    @property
    def definition(self) -> MetricDefinition:
        needs_k = self.kind in {"hit-rate-at-k", "mrr", "map", "ndcg"}
        config_properties: dict[str, Any] = {}
        required: list[str] = []
        if needs_k:
            config_properties["k"] = {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
            }
            required.append("k")
        return MetricDefinition(
            identifier=f"rag/{self.kind}",
            name=self.kind.replace("-", " ").upper(),
            version="1.0.0",
            description=f"Retrieval {self.kind} with explicit relevance denominators.",
            task_types=frozenset({TaskType.RAG}),
            required_fields=frozenset({"retrieved_items"}),
            output_schema=RESULT_SCHEMA,
            direction=(
                ScoreDirection.LOWER_IS_BETTER
                if self.kind == "duplicate-document-rate"
                else ScoreDirection.HIGHER_IS_BETTER
            ),
            minimum=0,
            maximum=1,
            reference_required=False,
            external_model_required=False,
            determinism=Determinism.DETERMINISTIC,
            aggregation="mean_available",
            failure_behavior=FailureBehavior.RETURN_MISSING,
            configuration_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": config_properties,
                "required": required,
            },
            computational_cost="O(retrieved ranks)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        config = configuration or {}
        identifiers = [str(item["id"]) for item in context.retrieved_items]
        k = int(config.get("k", max(1, len(identifiers))))
        if self.kind == "hit-rate-at-k":
            value = hit_rate_at_k(identifiers, context.relevant_item_ids, k)
        elif self.kind == "mrr":
            value = reciprocal_rank(identifiers, context.relevant_item_ids, k)
        elif self.kind == "map":
            value = average_precision(identifiers, context.relevant_item_ids, k)
        elif self.kind == "ndcg":
            relevance = {
                str(item["id"]): float(item.get("relevance", 0)) for item in context.retrieved_items
            }
            for identifier in context.relevant_item_ids:
                relevance.setdefault(identifier, 1.0)
            value = ndcg(identifiers, relevance, k)
        elif self.kind == "coverage":
            value = retrieval_coverage(identifiers, context.relevant_item_ids)
        else:
            value = duplicate_document_rate(identifiers)
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=value,
            missing=value is None,
            explanation="Required relevance labels are absent." if value is None else None,
            metadata={
                "retrieved_count": len(identifiers),
                "relevant_count": len(context.relevant_item_ids),
                "k": k if self.kind in {"hit-rate-at-k", "mrr", "map", "ndcg"} else None,
            },
        )


class CitationMetric:
    """Citation presence and source-ID validity metric."""

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier="rag/citation-validity",
            name="Citation validity",
            version="1.0.0",
            description="Fraction of explicit [source:ID] citations resolving to retrieved IDs.",
            task_types=frozenset({TaskType.RAG}),
            required_fields=frozenset({"prediction", "retrieved_items"}),
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
                "maxProperties": 0,
            },
            computational_cost="O(answer + retrieved items)",
            monetary_cost="none",
        )

    def evaluate(
        self, context: MetricContext, configuration: dict[str, Any] | None = None
    ) -> MetricResult:
        del configuration
        available = {str(item["id"]) for item in context.retrieved_items}
        values = citation_metrics(str(context.prediction), available)
        return MetricResult(
            self.definition.identifier,
            self.definition.version,
            scalar=float(values["validity"] or 0),
            structured=values,
        )
