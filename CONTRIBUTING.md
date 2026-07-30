# Contributing

Thank you for improving the LLM Evaluation Platform.

## Development contract

Use Python 3.12 or newer, Node 24.15 or newer, Docker with Compose v2, and `uv`.
Copy `.env.example` to `.env`, run `make install`, and execute `make verify`
before opening a change.

Production changes must include explicit types, behavioral tests, documentation,
and migrations when persistence changes. Domain packages may not import FastAPI,
Celery, SQLAlchemy, Redis, S3 clients, or provider implementations. New providers
and metrics implement the published contracts and pass their shared contract
suites.

Never commit credentials, customer data, copyrighted evaluation data without a
compatible license, generated reports containing sensitive content, or paid
provider recordings. Live-provider tests must use the `live_provider` marker and
are excluded from default CI.

## Change workflow

1. Create a focused branch.
2. Update the relevant requirement traceability row and documentation.
3. Add or revise an ADR for material architecture changes.
4. Implement code, migrations, documentation, and tests together.
5. Run `make verify`; run `make test-integration` for infrastructure changes.
6. Use a Conventional Commit such as `feat(dataset): add parquet import`.

Pull requests explain behavior, security/privacy implications, statistical
assumptions, operational rollout, and evidence from executed checks. Reviewers
reject silent missing-data handling, unbounded provider calls, weak tenant
scoping, or tests that only execute code without asserting outcomes.

## Releases

Maintainers update `CHANGELOG.md`, verify migration and API compatibility, run
the complete verification suite, tag `vMAJOR.MINOR.PATCH`, and publish artifacts
only from the protected release workflow. Breaking public API changes require a
major version or a documented deprecation window.
