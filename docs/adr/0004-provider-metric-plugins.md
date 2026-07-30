# ADR 0004: Vendor-neutral providers and typed metric plugins

- Status: Accepted
- Date: 2026-07-29

## Context

Core orchestration coupled to a vendor SDK or ad hoc metric function would
spread change across scheduling, persistence, APIs, and reports. Provider and
metric failures also need stable behavior.

## Decision

Define provider protocols for generation, chat, structured output, embeddings,
token estimation, capabilities, usage, tracing IDs, and normalized errors.
Implement fake, OpenAI-compatible, local OpenAI-compatible, and configurable
HTTP adapters with HTTPX rather than importing vendor SDKs.

Metrics use a registry and complete versioned definitions covering
compatibility, inputs, outputs, direction/range, reference needs, determinism,
aggregation, failure, and cost. Trusted built-ins run in process, and one
failure becomes one failed metric result.

## Consequences

Adapters and metrics can be added without changing domain orchestration.
Compatibility and provenance are inspectable through the API. Generic HTTP
configuration is intentionally constrained to a compatible schema rather than
executing arbitrary mappings or code. Untrusted plugins require a future
sandboxed worker pool.
