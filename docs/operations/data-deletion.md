# Data deletion and retention

Authorize deletion against organization/project scope and record requester,
legal basis, resource selection, and retention exceptions. Place the project in
a deletion hold while discovering dataset objects, responses, traces,
trajectories, reports, API keys, and backups.

Catalog deletion is soft first. Immutable versions referenced by completed
experiments are not edited; raw artifacts can be cryptographically erased or
deleted under policy while a tombstone preserves reproducibility limitations.
Delete object versions, then transactional metadata in foreign-key order after
the recovery window. Revoke credentials immediately.

Backups expire through documented lifecycle rather than ad-hoc editing. Provide
a deletion certificate containing counts and dates, not deleted content.
Verify cross-project resources were untouched.
