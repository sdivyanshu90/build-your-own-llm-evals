"""Built-in metric registry composition."""

from __future__ import annotations

from eval_platform_metrics.agent import (
    LoopDetectionMetric,
    RedundantToolCallMetric,
    ToolSuccessMetric,
)
from eval_platform_metrics.base import MetricRegistry, ScoreDirection
from eval_platform_metrics.language import (
    ClassificationAccuracyMetric,
    JsonSchemaMetric,
    JsonValidityMetric,
    MatchMetric,
    RegexMetric,
    SemanticSimilarityMetric,
    TextOverlapMetric,
    TokenF1Metric,
)
from eval_platform_metrics.operational import OperationalMetric
from eval_platform_metrics.rag import (
    CitationMetric,
    PrecisionAtKMetric,
    RecallAtKMetric,
    RetrievalRankingMetric,
)


def builtin_registry() -> MetricRegistry:
    """Return a fresh registry of stable built-in metric implementations."""

    registry = MetricRegistry()
    for metric in (
        MatchMetric("language/exact-match", "Exact match", "exact"),
        MatchMetric(
            "language/normalized-exact-match",
            "Normalized exact match",
            "normalized",
        ),
        MatchMetric(
            "language/case-insensitive-match",
            "Case-insensitive match",
            "case_insensitive",
        ),
        TokenF1Metric(),
        ClassificationAccuracyMetric(),
        JsonValidityMetric(),
        JsonSchemaMetric(),
        RegexMetric(),
        SemanticSimilarityMetric(),
        TextOverlapMetric("rouge-1"),
        TextOverlapMetric("rouge-2"),
        TextOverlapMetric("rouge-l"),
        TextOverlapMetric("bleu"),
        TextOverlapMetric("cer"),
        TextOverlapMetric("wer"),
        TextOverlapMetric("edit-distance"),
        RecallAtKMetric(),
        PrecisionAtKMetric(),
        RetrievalRankingMetric("hit-rate-at-k"),
        RetrievalRankingMetric("mrr"),
        RetrievalRankingMetric("map"),
        RetrievalRankingMetric("ndcg"),
        RetrievalRankingMetric("coverage"),
        RetrievalRankingMetric("duplicate-document-rate"),
        CitationMetric(),
        ToolSuccessMetric(),
        LoopDetectionMetric(),
        RedundantToolCallMetric(),
        OperationalMetric(
            "operations/latency-ms",
            "Latency",
            "latency_ms",
            ScoreDirection.LOWER_IS_BETTER,
            "ms",
        ),
        OperationalMetric(
            "operations/time-to-first-token-ms",
            "Time to first token",
            "ttft_ms",
            ScoreDirection.LOWER_IS_BETTER,
            "ms",
        ),
        OperationalMetric(
            "operations/input-tokens",
            "Input tokens",
            "input_tokens",
            ScoreDirection.NEUTRAL,
            "tokens",
        ),
        OperationalMetric(
            "operations/output-tokens",
            "Output tokens",
            "output_tokens",
            ScoreDirection.NEUTRAL,
            "tokens",
        ),
        OperationalMetric(
            "operations/total-tokens",
            "Total tokens",
            "total_tokens",
            ScoreDirection.NEUTRAL,
            "tokens",
        ),
        OperationalMetric(
            "operations/cost-usd",
            "Cost",
            "cost_usd",
            ScoreDirection.LOWER_IS_BETTER,
            "USD",
        ),
        OperationalMetric(
            "operations/retrieval-latency-ms",
            "Retrieval latency",
            "retrieval_latency_ms",
            ScoreDirection.LOWER_IS_BETTER,
            "ms",
        ),
        OperationalMetric(
            "operations/generation-latency-ms",
            "Generation latency",
            "generation_latency_ms",
            ScoreDirection.LOWER_IS_BETTER,
            "ms",
        ),
        OperationalMetric(
            "operations/end-to-end-latency-ms",
            "End-to-end latency",
            "end_to_end_latency_ms",
            ScoreDirection.LOWER_IS_BETTER,
            "ms",
        ),
        OperationalMetric(
            "operations/throughput-tokens-per-second",
            "Throughput",
            "throughput_tokens_per_second",
            ScoreDirection.HIGHER_IS_BETTER,
            "tokens/second",
        ),
        OperationalMetric(
            "operations/error",
            "Error indicator",
            "error",
            ScoreDirection.LOWER_IS_BETTER,
            "indicator",
        ),
        OperationalMetric(
            "operations/refusal",
            "Refusal indicator",
            "refusal",
            ScoreDirection.NEUTRAL,
            "indicator",
        ),
        OperationalMetric(
            "agent/step-count",
            "Agent step count",
            "step_count",
            ScoreDirection.NEUTRAL,
            "steps",
        ),
        OperationalMetric(
            "agent/tool-cost-usd",
            "Tool cost",
            "tool_cost_usd",
            ScoreDirection.LOWER_IS_BETTER,
            "USD",
        ),
    ):
        registry.register(metric)
    return registry
