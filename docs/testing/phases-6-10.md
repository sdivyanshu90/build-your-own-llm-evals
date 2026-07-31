# Phase 6–10 testing

Judge tests exercise strict JSON, missing/out-of-range fields, fence repair,
abstention, repeated aggregation, billed retries, malicious instructions,
position reversal, balance, disagreement, calibration, and drift.

Statistical tests compare hand examples and SciPy for Wilson, exact binomial,
t, and paired procedures. Fixed-seed bootstrap tests cover percentile, basic,
BCa, paired, stratified, cluster, median, degeneracy, all ties, missingness,
zero variance, and reproducibility. A deterministic binomial simulation checks
Wilson coverage within a prespecified Monte Carlo band.

Application tests verify paired alignment, explicit failure denominators,
practical interpretation, multiple comparisons, safe CSV, escaped HTML, and
gate exit semantics. Migration tests use real PostgreSQL. API isolation tests
must use two projects and assert cross-project IDs return not-found. Frontend
tests cover loading, empty, error, permission, missing-versus-zero, confidence
text, and keyboard-visible controls.

Run locally:

```bash
make verify
make test-integration
docker compose up --build -d
```

Use Node 24 or newer. Older Node releases cannot execute the pinned Vite/Vitest
toolchain. Live-provider tests remain opt-in and are excluded from default CI.
Performance scenarios use the fake provider and synthetic data to avoid spend.
