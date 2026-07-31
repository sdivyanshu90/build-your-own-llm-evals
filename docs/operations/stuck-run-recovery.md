# Stuck-run recovery

A run is suspected stuck when it is non-terminal, has pending tasks, no
settlement progress, and no valid active leases beyond the configured alert
window.

1. Confirm scheduler, relay, worker, Redis, PostgreSQL, and provider health.
2. Query task states and lease expiry; do not modify successful tasks.
3. Let active leases expire or terminate the owning worker gracefully.
4. Requeue only queued tasks and expired leased/running tasks.
5. Recompute run counters from terminal sample/task rows.
6. Resume the run through its legal state transition.
7. Verify actual/ambiguous cost before restoring dispatch.

Manual SQL state changes bypass invariants and are an emergency last resort.
Take a database snapshot, use a reviewed transaction, append an audit event,
and run the state-machine reconciliation check afterward.
