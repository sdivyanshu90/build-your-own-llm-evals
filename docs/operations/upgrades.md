# Upgrade procedure

1. Review changelog, dependency diffs, provider contracts, and migration plan.
2. Back up PostgreSQL and capture object inventory and audit checkpoint.
3. Run CI, fresh migration, prior-release upgrade, fake demo, and restore drill.
4. Apply additive schema migration.
5. Canary API with workers paused; verify health, OpenAPI, auth, RLS, and reads.
6. Roll workers gradually and run deterministic evaluations.
7. Monitor queue, errors, retries, latency, judge validation, and cost.
8. Complete backfills before any contract migration in a later release.

Application rollback is safe only while the old binary understands the expanded
schema. Database downgrades are not the routine rollback mechanism; restore a
verified backup when a destructive migration must be reversed.
