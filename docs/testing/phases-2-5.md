# Testing Phases 2–5

The default backend suite does not require paid APIs or infrastructure. It uses
the deterministic fake provider, hand-calculated metrics, in-memory repository
fakes, generated records, and fixed seeds.

Unit and property tests cover UUID monotonicity, decimal money, authorization,
every run-state pair, canonical equivalence and idempotence, golden hashes,
dataset diff/sampling/redaction/MinHash behavior, all import formats, retry
classification and deterministic jitter, safe settings and key handling,
provider contract behavior, language metrics, retrieval denominators, agent
trajectories, and object-key traversal defenses.

The fake provider contract asserts generation, structured output validation,
usage, deterministic embeddings, error normalization, retryability, and that
no paid service is required. New adapters must pass the same contract with a
deterministic fake HTTP server.

Run locally:

```bash
uv run pytest -m "not integration and not performance and not live_provider"
uv run coverage run -m pytest -m "not integration and not performance and not live_provider"
uv run coverage report
```

Integration verification starts PostgreSQL, applies every Alembic migration
from empty, seeds a canonical version, executes the fake-provider run, and
checks durable samples/metrics. Reset-test migration validation must use an
isolated database because downgrade or volume deletion is destructive.

Numerical tolerances are explicit in metric assertions. Exact discrete formulas
use exact equality; floating transforms use `pytest.approx` at a tolerance
smaller than the score precision presented to users. Statistical simulation,
confidence-interval coverage, paired tests, and ranking validation arrive with
the dedicated Phase 7 package. Property checks disable Hypothesis timing
deadlines when the property is not a performance claim; performance thresholds
remain in explicitly marked, environment-described scenarios.

The current frontend test uses Testing Library to assert the accessible empty
project state and required organization control. The production bundle also
passes Prettier, ESLint, strict TypeScript, Vitest, Vite, and high-severity npm
audit. Loading, error, permission, successful-data, and full Playwright
workflows remain Phase 8 work.
