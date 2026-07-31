# Backup and restore

## Recovery objectives

Set business-specific RPO/RTO before deployment. A representative target is
PostgreSQL RPO 5 minutes/RTO 60 minutes, object storage RPO 15 minutes/RTO 4
hours, and Redis RPO zero because authoritative data must not depend on Redis.

## Backup

Enable PostgreSQL continuous WAL archiving plus daily encrypted snapshots and
retain a cross-account copy. Enable object versioning, lifecycle protection,
and inventory reports. Export deployment configuration, image digests,
migration revision, and audit-chain checkpoints. Back up Redis only to reduce
queue replay time, never as the sole copy of run state.

Test restoration monthly into an isolated account:

1. restore PostgreSQL to a chosen timestamp;
2. restore or mount a consistent object-store version;
3. deploy the recorded application image;
4. run `alembic current` and `alembic upgrade head` only after compatibility review;
5. reconcile artifact descriptors against objects;
6. expire stale leases and replay unpublished outbox events;
7. compare run/sample/metric/cost counts and audit hashes;
8. execute a deterministic fake evaluation and report export.

Do not point restored workers at production providers until budget ledgers and
queued tasks are reconciled; otherwise replay can create duplicate spend.
