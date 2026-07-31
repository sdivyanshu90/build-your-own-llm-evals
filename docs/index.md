# LLM Evaluation Platform

This repository provides the executable foundation for reproducible offline
evaluation of language models, retrieval-augmented generation systems, and
tool-using agents. Phases 2–5 implement the platform foundation, immutable
dataset registry, resumable execution engine, provider boundary, and
code-metric framework. Pairwise judging and inferential statistics remain
explicitly scheduled for Phases 6 and 7.

The central design rule is that evidence must be reconstructable. A result is
therefore linked to canonical dataset bytes, an immutable system snapshot,
versioned metric definitions, random seeds, a dependency-lock digest, provider
request metadata, explicit failures, and denominators that include missing
samples.

## Executable path

```bash
cp .env.example .env
make dev-up
make seed
make demo
```

The API is served at `http://localhost:8000`, OpenAPI at
`http://localhost:8000/api/docs`, the dashboard at
`http://localhost:5173`, and the MinIO console at
`http://localhost:59001`.

The demo is synthetic and uses the deterministic fake provider. It requires no
paid API and sends no data outside the local Compose network.

## Read next

- [Platform foundation](architecture/platform-foundation.md) explains service
  boundaries, storage, transactions, tenancy, and observability.
- [Versioned datasets](concepts/versioned-datasets.md) specifies canonical
  identity, publication, diffs, sampling, redaction, and contamination checks.
- [Evaluation engine](concepts/evaluation-engine.md) explains snapshots,
  state transitions, leases, retry classification, budgets, and recovery.
- [Metric framework](concepts/metric-framework.md) describes compatibility,
  denominators, isolation, language, RAG, agent, and operational metrics.
- [Phase 1 design](design/phase-1-design.md) and the
  [traceability matrix](design/requirement-traceability-matrix.md) define the
  full ten-phase target.
