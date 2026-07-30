# ADR 0001: Platform foundation

- **Status:** Accepted
- **Date:** 2026-07-29
- **Decision owners:** Platform architecture
- **Supersedes:** Nothing

## Context

The platform needs strong transactional behavior, asynchronous provider calls,
large immutable artifacts, statistically auditable outputs, multiple user
interfaces, and extension points for providers and metrics. It must be usable on
one developer machine and scale horizontally without putting vendor concerns in
domain logic.

## Decision

Build a Python 3.12+ and TypeScript monorepo as a clean-architecture modular
monolith. Deploy FastAPI and Celery as separate processes. Use PostgreSQL as the
durable system of record, Redis as a disposable Celery broker and coordination
cache, and S3-compatible storage for large immutable artifacts. Publish work
through a transactional outbox and make consumers idempotent.

Use immutable numbered versions for datasets and evaluation configuration,
schema-aware RFC-8785-based canonicalization with SHA-256 content hashes, UUIDv7
identifiers, project-scoped RBAC with PostgreSQL RLS defense in depth, and
versioned plugin contracts for providers and metrics.

Use NumPy, SciPy, and statsmodels as statistical primitives, with platform-owned
typed procedures for paired alignment, missingness, provenance, warnings, and
interpretation. Use React and TypeScript for the web dashboard, a generated
OpenAPI-aware SDK, and Typer for `evalctl`.

Use OpenTelemetry, JSON logs, and Prometheus metrics. Package local dependencies
with Docker Compose and production deployment with multi-stage non-root images
and Kustomize Kubernetes manifests.

Exact dependency releases are not part of this ADR. They will be checked against
official release sources and pinned in Phase 2.

## Consequences

Positive consequences:

- domain and statistical logic remain testable without infrastructure;
- PostgreSQL transactions and constraints protect core invariants;
- API and workers can scale separately;
- the outbox and stable contracts permit later service extraction;
- S3 keeps large traces out of hot relational rows;
- deterministic fake adapters support a paid-service-free test and demo path.

Costs and constraints:

- at-least-once task delivery requires explicit leases and idempotency;
- RLS, application authorization, and composite tenant foreign keys require
  duplicate but deliberately layered controls;
- object/database consistency requires staged writes and reconciliation;
- two language toolchains and lockfiles increase CI work;
- a modular monolith needs dependency checks to prevent boundary erosion.

## Alternatives considered

### Microservices from the first release

Rejected because distributed transactions, contract deployment, local operation,
and incident response would add risk before module load profiles are known. The
outbox and ports preserve a migration path.

### SQLite as the primary database

Rejected because row-level security, concurrent leasing, robust constraints,
partitioning, and production parity are required. SQLite may be used only in
isolated pure adapter tests, never as a supported deployment database.

### Redis as result backend and source of run state

Rejected because Redis is treated as recoverable coordination infrastructure.
Durable state, attempts, progress, and costs belong in PostgreSQL/object storage.

### Vendor SDKs in evaluation services

Rejected because vendor types and error semantics would leak into core logic.
Adapters use `httpx` and normalize all capabilities, usage, tracing, and errors.

### Arbitrary user Python metric plugins in shared workers

Rejected for the initial release due to remote-code-execution and isolation
risks. Built-in and installed, allowlisted packages use a versioned contract.
Untrusted custom code requires a future sandboxed executor ADR.

### Elo as the primary ranking model

Rejected because order and tuning affect sequential Elo. Batch
Bradley–Terry/Davidson models are primary; Elo remains an explicitly descriptive
optional view.

## Follow-up ADRs

Later phases will split this foundation into focused ADRs for monorepo layout,
database and tenancy, queue/outbox semantics, object storage, clean boundaries,
dataset hashing, immutability, provider contracts, metric plugins, statistics,
judge schemas, observability, and deployment. Those ADRs may refine but must
explicitly supersede any conflicting statement here.

## Validation

The architectural decision is validated by:

- import-boundary tests;
- migration, RLS, task duplicate, outbox, and object reconciliation integration
  tests;
- provider and metric contract suites;
- deterministic end-to-end demonstration;
- non-root container and Kubernetes manifest checks;
- the requirement acceptance criteria linked from the traceability matrix.
