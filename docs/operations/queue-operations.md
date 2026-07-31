# Queue operations

Inspect generation, metric, and maintenance queue depth, oldest-message age,
worker heartbeats, task settlement rate, retries, provider limits, and database
pool saturation together.

For a growing queue:

1. determine whether throughput stopped or arrival rate merely increased;
2. inspect normalized failure and retry categories;
3. stop dispatch if provider rate limits or budgets are the bottleneck;
4. scale workers only within provider and database concurrency budgets;
5. isolate a poison task by natural key and inspect sanitized attempts;
6. pause affected runs rather than purging durable work.

Do not delete broker messages as a normal recovery action. At-least-once
delivery and leases make replay safe, while an indiscriminate purge can strand
queued database tasks. If Redis is rebuilt, re-enqueue non-terminal tasks from
PostgreSQL in bounded windows and record the operation in audit history.
