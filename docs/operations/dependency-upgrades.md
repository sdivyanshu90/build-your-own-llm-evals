# Dependency upgrades

Direct Python and JavaScript dependencies are exactly pinned. `uv.lock` and
`package-lock.json` lock the transitive graphs. Container base tags are pinned
to explicit releases; production releases should additionally record resolved
image digests and an SBOM.

Versions for the Phase 2 baseline were checked against official PyPI JSON,
the npm registry, the uv release page, and upstream container registries on
2026-07-29. A dependency was not selected solely because it was newest:
TypeScript 7 was rejected after npm reported that the pinned
`typescript-eslint` version only accepts TypeScript below 6.1; TypeScript 6.0.3
is the compatible stable pin. React Router 7.18.2 was also rejected after the
official advisory feed reported a high-severity RSC vulnerability without a
published patched npm release. The dashboard uses TanStack Router 1.170.18;
`npm audit --audit-level=high` is a required CI gate.

Upgrade procedure:

1. Review release notes, Python/Node support, security advisories, licenses,
   and peer constraints.
2. Change one coherent dependency family at a time; OpenTelemetry API, SDK,
   exporters, semantic conventions, and instrumentations move together.
3. Regenerate the relevant lock with `uv lock --upgrade-package NAME` or
   `npm install --package-lock-only`.
4. Inspect lock diffs for unexpected sources, native wheels, and license
   changes.
5. Run format, lint, strict types, unit/property/contract tests, migrations,
   documentation, frontend build/tests, package builds, and container smoke
   tests.
6. For numerical libraries, compare golden examples and statistical tolerances;
   for canonicalization libraries, prove historical hashes unchanged.
7. Deploy to staging, observe database pool, queue, provider error, latency,
   and cost metrics, then release semantically.

Dependabot opens weekly grouped changes. Automated pull requests do not bypass
quality gates. Security patches can be expedited, but a production hotfix still
needs migration and rollback analysis.
