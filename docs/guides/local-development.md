# Local development

## Prerequisites

Install Docker with Compose v2. For host-side development, install Python 3.12,
uv 0.12, and Node.js 24.15 or newer. Container-only users do not need local
Python, Node, PostgreSQL, Redis, or MinIO.

## Start the stack

```bash
cp .env.example .env
make dev-up
```

Compose applies migrations before API and worker startup. Containers run as
non-root except upstream dependency images that define their own runtime user.
Default local ports are PostgreSQL `55432`, Redis `56379`, API `8000`, MinIO
`59000/59001`, and web `5173`. The high infrastructure ports reduce
collisions with workstation services and are configurable through the
`EVAL_*_HOST_PORT` values in `.env`; service-to-service connections retain
their standard container ports.

Seed and run the no-network demonstration:

```bash
make seed
make demo
```

The stable development organization is
`01900000-0000-7000-8000-000000000001`. Development identity headers are a
local convenience, not authentication; the application refuses that mode when
`EVAL_ENVIRONMENT=production`.

## Host checks

```bash
uv sync --all-extras --frozen
make lint
make format-check
make typecheck
make test
make docs
npm ci
npm test
npm run typecheck
npm run build
```

Integration tests and container builds are separate because they require the
Docker daemon. Paid-provider tests are always opt-in and are excluded from the
default CI markers.

## Stop and reset

`make dev-down` stops containers and retains named volumes. To intentionally
destroy local PostgreSQL, Redis, and MinIO data, use
`docker compose down --volumes` only after confirming that the Compose project
contains no evidence you need.
