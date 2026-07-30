"""Prometheus and OpenTelemetry initialization."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "eval_http_requests_total",
    "API requests by method, route template, and status.",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "eval_http_request_duration_seconds",
    "API request duration by route template.",
    ("method", "route"),
)
RUNS = Counter("eval_runs_total", "Evaluation runs by terminal status.", ("status",))
TASK_FAILURES = Counter(
    "eval_task_failures_total",
    "Task failures by stable category.",
    ("category", "retryable"),
)
PROVIDER_DURATION = Histogram(
    "eval_provider_duration_seconds",
    "Provider request latency.",
    ("provider_type", "operation"),
)
QUEUE_DEPTH = Gauge("eval_queue_depth", "Known queue depth.", ("queue",))
TOKENS = Counter("eval_tokens_total", "Provider token usage.", ("kind", "provider_type"))
COST = Counter("eval_cost_usd_total", "Recorded provider cost in USD.", ("provider_type",))
RETRIES = Counter(
    "eval_retries_total",
    "Retry attempts by stable operation and failure category.",
    ("operation", "category"),
)
RUN_DURATION = Histogram(
    "eval_run_duration_seconds",
    "Terminal evaluation run duration.",
    ("status",),
    buckets=(10, 30, 60, 300, 900, 3600, 14_400, 86_400),
)
EVALUATION_THROUGHPUT = Counter(
    "eval_samples_settled_total",
    "Settled evaluation samples by status.",
    ("status",),
)
JUDGE_DISAGREEMENT = Histogram(
    "eval_judge_disagreement_ratio",
    "Observed disagreement ratio for repeated judgments.",
    buckets=(0, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1),
)
JUDGE_VALIDATION_FAILURES = Counter(
    "eval_judge_validation_failures_total",
    "Strict judge output validation failures.",
    ("judge_identifier",),
)
BUDGET_BREACHES = Counter(
    "eval_budget_breaches_total",
    "Rejected work due to configured cost budgets.",
    ("scope",),
)


def configure_tracing(service_name: str, version: str, endpoint: str) -> None:
    """Configure OTLP tracing when an endpoint is supplied."""

    if not endpoint:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name, "service.version": version})
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
