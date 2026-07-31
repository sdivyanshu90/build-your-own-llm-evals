# Secret rotation

Provider and object-store keys should support overlapping old/new credentials.
Inject the new version, restart workers gradually, verify canary calls, revoke
the old version, and scan logs/errors for stale consumers.

API-key pepper rotation invalidates existing digests unless dual-pepper
verification is deployed for a bounded migration window. Prefer scheduled mass
key replacement: create new service keys, update consumers, revoke old keys,
then replace the pepper.

Database and Redis credentials require connection-drain planning. Update the
managed service, secret manager, migration jobs, API, scheduler, and workers;
verify no old sessions remain. Audit only credential identifiers and rotation
outcomes, never secret values.
