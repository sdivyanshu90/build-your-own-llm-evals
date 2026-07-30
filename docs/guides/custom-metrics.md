# Custom metrics

Implement the metric protocol in `packages/metrics`, then register one instance
in `builtin_registry`. A metric definition must be complete enough for users
and schedulers to reason about applicability and cost before execution.

Choose a namespaced stable identifier such as `acme/factual-field-accuracy`.
Increment the version whenever normalization, required fields, denominator,
range, direction, aggregation, output schema, or external dependency changes.
Do not overwrite historical semantics.

The evaluation method receives a `MetricContext` and validated configuration.
Return a typed `MetricResult`. If the metric cannot apply because a reference
or trace is absent, return missing rather than zero. Raise
`MetricExecutionError` for an attempted calculation that failed. Never catch
broad exceptions and fabricate a score.

Tests should include:

- a hand-calculated ordinary case;
- empty input, absent reference, duplicate value, and invalid configuration;
- lower and upper range boundaries;
- task compatibility and result schema;
- deterministic repeatability or explicit seeded behavior;
- denominator behavior;
- proof that plugin failure leaves unrelated results intact.

Model-backed metrics should use the provider/judge boundary, declare monetary
and computational cost, store evidence references and concise justification,
and avoid requesting hidden chain-of-thought. Full judge plugins are introduced
in Phase 6.
