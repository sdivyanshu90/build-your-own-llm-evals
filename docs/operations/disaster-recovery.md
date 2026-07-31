# Disaster recovery

Declare disaster when the primary region cannot meet RTO or data integrity is
uncertain. Freeze provider work to prevent split-brain spend. Select a
PostgreSQL recovery point, object-store inventory/version, application image,
and migration revision from the same recovery envelope.

Restore dependencies and application in the order described in
[Backup and restore](backup-restore.md). Change DNS only after write fencing,
tenant isolation checks, audit checkpoint validation, fake-provider workflow,
and budget reconciliation pass. Treat a return to the primary region as a
second migration with the same fencing and reconciliation requirements.

The platform does not claim active-active cross-region writes. UUIDs reduce ID
collision risk but do not resolve concurrent state transitions or ledger
conflicts.
