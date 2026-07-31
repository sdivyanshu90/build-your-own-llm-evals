# Production deployment

## External prerequisites

Provision multi-zone PostgreSQL 17+, Redis 8+, versioned S3-compatible storage,
an OTLP collector, Prometheus, ingress TLS, DNS, and a secret manager. The
included dependency containers are local-development services, not a
high-availability production data plane.

Build and sign immutable backend and web images. Replace image references and
the invalid example domain in `deploy/kubernetes`. Create
`llm-eval-secrets` through External Secrets, CSI Secret Store, or equivalent;
do not apply `secret.example.yaml`.

```bash
kubectl apply -k deploy/kubernetes
kubectl -n llm-eval wait --for=condition=complete job/llm-eval-migrate --timeout=5m
kubectl -n llm-eval rollout status deployment/llm-eval-api
kubectl -n llm-eval rollout status deployment/llm-eval-worker
```

The migration job must complete before new application pods receive traffic.
For backwards-incompatible database changes use expand, deploy, backfill,
contract across separate releases.

## Security checks

- Production mode rejects header authentication, a development pepper, and
  disabled distributed rate limiting.
- Pods run non-root under restricted Pod Security with dropped capabilities.
- API and worker filesystems are read-only except bounded temporary volumes.
- Network policy denies unsolicited traffic and permits provider HTTPS.
- TLS terminates at ingress; use TLS again to managed dependencies.
- Prefer workload identity over static object-store credentials.

## Sizing and scaling

Start from manifest requests, measure, and revise. API HPA targets CPU; worker
HPA targets queue depth. Provider concurrency and database connections must be
bounded across all replicas. A worker replica with concurrency four may consume
four database/provider slots plus maintenance work. Keep at least 30% database
connection headroom for migrations and incident access.

## Verification

Check migrations, readiness, Prometheus target health, one deterministic fake
run, cancellation/resumption, report export, audit events, and backup restore
before enabling remote providers. Load-test with synthetic records and a fake
provider so the test does not create uncontrolled spend.
