# Evaluation runs

## Create an experiment

An experiment request supplies:

- a published dataset version ID;
- provider type, identifier, base URL or local fake responses, and secret
  environment-variable reference;
- model identifier, prompt containing `{{ input }}`, and model parameters;
- suite task type, input/reference field names, and versioned metric IDs;
- an unsigned 64-bit seed.

Provider dictionaries containing fields such as `api_key`, `password`,
`access_token`, or `authorization` are rejected. Inject the corresponding
environment secret into worker containers and store only `secret_env`.

## Start and inspect

Starting a run supplies repetitions and a decimal budget. It returns `202` after
the durable task set and outbox event commit. Poll
`GET /api/v1/projects/{project_id}/runs/{run_id}` for counts and state; list
results to inspect successful and failed records. Aggregates display sample and
missing/failure counts, never a point estimate alone.

Pause affects new task claims, not an in-flight remote request. Resume republishes
the same run and preserves terminal work. Cancellation is cooperative. A
terminal run is reproduced by starting a new run from the immutable experiment.

## Local deterministic example

```bash
make demo
```

The command seeds three synthetic QA records, snapshots a fake provider,
creates three tasks, executes exact-match and latency metrics, and prints IDs,
state, sample count, metric-result count, failures, cost, and a reproduction
hint. No external network or provider credential is used.

## Diagnosing failures

Inspect failure category and normalized provider kind before deciding to retry.
Rate-limit, timeout, connection, and server failures may be transient.
Authentication, permission, context length, invalid request, policy rejection,
and malformed structured output usually require configuration or input changes.
An ambiguous billing marker means a provider may have accepted a request
without returning a response; check its request logs using the persisted
idempotency key and provider request ID when available.
