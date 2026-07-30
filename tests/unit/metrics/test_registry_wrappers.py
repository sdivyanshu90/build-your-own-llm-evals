"""Plugin registry compatibility, wrappers, aggregation, and isolation tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from eval_platform_metrics.aggregation import aggregate_mean
from eval_platform_metrics.base import (
    EMPTY_CONFIG_SCHEMA,
    RESULT_SCHEMA,
    Determinism,
    FailureBehavior,
    MetricContext,
    MetricDefinition,
    MetricExecutionError,
    MetricRegistry,
    MetricResult,
    ScoreDirection,
    TaskType,
)
from eval_platform_metrics.registry import builtin_registry


def test_all_language_metric_wrappers_execute_with_valid_configuration() -> None:
    registry = builtin_registry()
    ordinary = MetricContext(
        task_type=TaskType.GENERATION,
        input="question",
        prediction="Paris",
        reference="Paris",
    )
    for identifier in (
        "language/exact-match",
        "language/normalized-exact-match",
        "language/case-insensitive-match",
        "language/token-f1",
        "language/rouge-1",
        "language/rouge-2",
        "language/rouge-l",
        "language/bleu",
        "language/cer",
        "language/wer",
        "language/edit-distance",
    ):
        result = registry.evaluate(identifier, ordinary, {})
        assert result.metric_id == identifier
        assert result.scalar is not None

    json_context = MetricContext(
        task_type=TaskType.EXTRACTION,
        prediction='{"answer":"Paris"}',
        reference={"answer": "Paris"},
    )
    assert registry.evaluate("language/json-validity", json_context, {}).scalar == 1
    assert (
        registry.evaluate(
            "language/json-schema-compliance",
            json_context,
            {
                "schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                }
            },
        ).scalar
        == 1
    )
    assert (
        registry.evaluate(
            "language/regex-match",
            ordinary,
            {"pattern": "^Par", "full_match": False},
        ).scalar
        == 1
    )
    assert registry.evaluate(
        "language/semantic-similarity",
        MetricContext(
            task_type=TaskType.GENERATION,
            prediction="Paris",
            reference="Paris",
        ),
        {
            "prediction_embedding": [1.0, 0.0],
            "reference_embedding": [1.0, 0.0],
            "embedding_model": "fake/embed-v1",
        },
    ).scalar == pytest.approx(1)
    assert (
        registry.evaluate(
            "language/classification-accuracy",
            MetricContext(
                task_type=TaskType.CLASSIFICATION,
                prediction="positive",
                reference="positive",
            ),
            {},
        ).scalar
        == 1
    )


def test_rag_agent_and_operational_wrappers_execute() -> None:
    registry = builtin_registry()
    retrieved = (
        {"id": "a", "relevance": 3},
        {"id": "b", "relevance": 0},
        {"id": "a", "relevance": 3},
    )
    rag = MetricContext(
        task_type=TaskType.RAG,
        prediction="Answer [source:a]",
        retrieved_items=retrieved,
        relevant_item_ids=frozenset({"a", "c"}),
    )
    for identifier in (
        "rag/recall-at-k",
        "rag/precision-at-k",
        "rag/hit-rate-at-k",
        "rag/mrr",
        "rag/map",
        "rag/ndcg",
    ):
        result = registry.evaluate(identifier, rag, {"k": 3})
        assert result.scalar is not None
    for identifier in ("rag/coverage", "rag/duplicate-document-rate"):
        assert registry.evaluate(identifier, rag, {}).scalar is not None
    assert registry.evaluate("rag/citation-validity", rag, {}).scalar == 1

    trajectory = (
        {"kind": "tool_call", "tool": "search", "arguments": {"q": "x"}},
        {"kind": "tool_result", "tool": "search", "success": True, "output": "x"},
        {"kind": "tool_call", "tool": "search", "arguments": {"q": "x"}},
    )
    agent = MetricContext(task_type=TaskType.AGENT, trajectory=trajectory)
    assert registry.evaluate("agent/tool-call-success-rate", agent, {}).scalar == 1
    assert registry.evaluate(
        "agent/loop-detected",
        agent,
        {"minimum_repetitions": 2},
    ).scalar in {0, 1}
    assert registry.evaluate("agent/redundant-tool-call-rate", agent, {}).scalar > 0

    operational = MetricContext(
        task_type=TaskType.GENERATION,
        operational={
            "latency_ms": 12,
            "ttft_ms": 4,
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
            "cost_usd": 0.001,
            "throughput_tokens_per_second": 100,
            "error": 0,
            "refusal": 0,
        },
    )
    for identifier in (
        "operations/latency-ms",
        "operations/time-to-first-token-ms",
        "operations/input-tokens",
        "operations/output-tokens",
        "operations/total-tokens",
        "operations/cost-usd",
        "operations/throughput-tokens-per-second",
        "operations/error",
        "operations/refusal",
    ):
        assert registry.evaluate(identifier, operational, {}).scalar is not None


@dataclass
class BrokenMetric:
    mode: str

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            identifier=f"test/{self.mode}",
            name="Broken",
            version="1",
            description="test",
            task_types=frozenset({TaskType.GENERATION}),
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
            computational_cost="test",
            monetary_cost="none",
        )

    def evaluate(
        self,
        context: MetricContext,
        configuration: dict[str, Any] | None = None,
    ) -> MetricResult:
        del context, configuration
        if self.mode == "exception":
            raise ValueError("isolated")
        return MetricResult(f"test/{self.mode}", "1", scalar=2)


def test_registry_rejects_conflicts_missing_inputs_incompatibility_and_bad_results() -> None:
    registry = MetricRegistry()
    metric = BrokenMetric("exception")
    registry.register(metric)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(metric)
    with pytest.raises(MetricExecutionError, match="not registered"):
        registry.definition("unknown")
    with pytest.raises(MetricExecutionError, match="does not support"):
        registry.evaluate(
            "test/exception",
            MetricContext(task_type=TaskType.RAG, prediction="x"),
            {},
        )
    with pytest.raises(MetricExecutionError, match="missing"):
        registry.evaluate(
            "test/exception",
            MetricContext(task_type=TaskType.GENERATION),
            {},
        )
    with pytest.raises(MetricExecutionError, match="isolated"):
        registry.evaluate(
            "test/exception",
            MetricContext(task_type=TaskType.GENERATION, prediction="x"),
            {},
        )
    out_of_range = BrokenMetric("range")
    registry.register(out_of_range)
    with pytest.raises(MetricExecutionError, match="above its range"):
        registry.evaluate(
            "test/range",
            MetricContext(task_type=TaskType.GENERATION, prediction="x"),
            {},
        )


def test_aggregate_mean_partitions_available_missing_and_failed() -> None:
    aggregate = aggregate_mean(
        [
            MetricResult("metric", "1", scalar=1),
            MetricResult("metric", "1", scalar=0),
            MetricResult("metric", "1", missing=True),
            MetricResult("metric", "1", scalar=float("nan")),
        ],
        failed_count=2,
    )
    assert aggregate.value == 0.5
    assert aggregate.total_count == 6
    assert aggregate.available_count == 2
    assert aggregate.missing_count == 2
    assert aggregate.failed_count == 2
