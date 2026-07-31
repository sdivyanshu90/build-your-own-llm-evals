# ADR 0006: Stateless services with managed durable dependencies

- Status: Accepted
- Date: 2026-07-30

## Context

The platform must scale API and provider work independently, survive
at-least-once delivery, provide durable audit and result state, and operate with
restricted tenant access.

## Decision

Deploy stateless API, worker, scheduler, and web containers to Kubernetes.
PostgreSQL is the durable source of truth, S3-compatible storage holds large
artifacts, and Redis provides disposable queue/coordination state. Production
uses managed multi-zone dependencies and external secret injection. Containers
run as non-root with restricted pod security, resource limits, read-only roots,
network policy, probes, autoscaling, and disruption budgets.

Migrations run as an explicit pre-rollout job. Releases are blocked by lint,
types, behavior tests, documentation, dependency/source/secret/image scans,
package builds, and SBOM generation.

## Consequences

Application replicas scale horizontally and can be replaced without local
state. Operators must provision and back up three dependency classes and
monitor queue/database/object-store health. Redis loss may delay work but cannot
be allowed to erase authoritative experiment results.
