# ADR 0003: Celery plus PostgreSQL outbox and leases

- Status: Accepted
- Date: 2026-07-29

## Context

Evaluation calls are slow, rate-limited, costly, and failure-prone. The broker
cannot be the source of truth, and exactly-once delivery is not available
across PostgreSQL, Redis, and remote providers.

## Decision

Use Celery with Redis for delivery and PostgreSQL for run/task truth. Commit a
bounded task set and outbox event atomically. Relay at least once. Claim tasks
with row locks and expiring leases; protect results with natural uniqueness,
terminal-state checks, and transactions. Supply deterministic provider
idempotency keys where supported.

## Consequences

Queue loss is recoverable and workers scale horizontally. Duplicate messages
do not duplicate durable results. A crash around a remote call may still cause
ambiguous billing, which is recorded rather than hidden. Distributed
provider/project concurrency semaphores and cost reservation are required
before multi-task parallel dispatch.
