# Configuration

All application variables use the `EVAL_` prefix. `.env.example` contains safe
local values and empty external credential slots. Compose reads `.env`; secret
managers should inject production values directly rather than baking them into
images.

| Variable | Meaning | Production rule |
| --- | --- | --- |
| `EVAL_ENVIRONMENT` | `development`, `test`, or `production` | use `production` |
| `EVAL_AUTH_MODE` | development headers or API keys | must be `api_key` |
| `EVAL_DATABASE_URL` | async SQLAlchemy PostgreSQL URL | TLS and least-privilege role |
| `EVAL_REDIS_URL` | disposable coordination database | private network and TLS |
| `EVAL_CELERY_BROKER_URL` | Celery broker database | no-eviction policy |
| `EVAL_S3_ENDPOINT_URL` | S3-compatible endpoint | TLS and egress allowlist |
| `EVAL_S3_BUCKET` | artifact bucket | versioning/lifecycle policy |
| `EVAL_API_KEY_PEPPER` | HMAC pepper | unique secret, rotate deliberately |
| `EVAL_MAX_UPLOAD_BYTES` | upload body bound | size for worker/API memory |
| `EVAL_MAX_IMPORT_RECORDS` | import record bound | align to plan/quota |
| `EVAL_MAX_RESPONSE_BYTES` | provider response bound | keep bounded |
| `EVAL_RATE_LIMIT_ENABLED` | Redis-coordinated API limit | must be `true` |
| `EVAL_RATE_LIMIT_REQUESTS_PER_MINUTE` | fixed-window requests per caller | size with edge/WAF limits |
| `EVAL_DISPATCH_WINDOW` | maximum records materialized into one run creation | tune below transaction and memory limits |
| `EVAL_OUTBOX_RELAY_INTERVAL_SECONDS` | bounded relay cadence, 1–60 seconds | size for queue latency and database load |
| `EVAL_WORKER_CONCURRENCY` | Compose worker process count | size against provider, CPU, memory, and database limits |
| `EVAL_PROVIDER_TIMEOUT_SECONDS` | per-attempt timeout | below gateway deadline |
| `EVAL_PROVIDER_MAX_ATTEMPTS` | total attempts | include cost/rate budget |
| `EVAL_DEFAULT_BUDGET_USD` | new project budget | explicit organization policy |
| `EVAL_OTLP_ENDPOINT` | OTLP collector URL | empty disables export |

The `EVAL_POSTGRES_HOST_PORT`, `EVAL_REDIS_HOST_PORT`,
`EVAL_MINIO_HOST_PORT`, and `EVAL_MINIO_CONSOLE_HOST_PORT` settings affect
only local Compose diagnostic bindings. They do not alter container-to-
container URLs and should normally be omitted from production orchestration.

Production startup fails if development authentication or the documented
development pepper is present, or if distributed rate limiting is disabled.
The API readiness probe requires PostgreSQL, Redis, and the configured object
store; liveness checks only the process loop. Provider secrets are named by experiment
configuration but read only from the worker environment. Rotate a provider
secret in the secret manager, restart workers gracefully, verify new requests,
then revoke the old value. Scrub credentials from shell history and incident
artifacts.

Back up PostgreSQL with point-in-time recovery and object storage with
versioning/replication appropriate to retention obligations. Redis is not a
backup source. Restore PostgreSQL and object storage to a consistent recovery
point, apply migrations, then rebuild queue work from the outbox and durable
nonterminal tasks.
