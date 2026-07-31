# General incident response

## API errors

Check target health, release/change timeline, PostgreSQL pool and locks, Redis,
object store, provider calls, route-level error rate, and p99 latency. Roll back
application code only when the previous image is compatible with the current
database expansion. Preserve request/trace IDs and sanitized logs.

## Latency

Separate ingress, API, database, object storage, queue, provider, and judge
latency. A slow provider must not be treated as API CPU pressure. Confirm
pagination bounds and query plans before scaling replicas.

## Dependency unavailable

PostgreSQL failure makes readiness fail and stops authoritative mutations.
Redis failure stops distributed rate limiting and queued work. Object-store
failure stops large artifact publication. Restore in that order, then
reconcile leases/outbox/artifacts.

For every severity-page incident: appoint incident commander, record UTC
timeline, contain cost/data exposure, communicate tenant impact, preserve
evidence, restore with a canary, and publish corrective actions with owners and
dates in the organization’s incident system.
