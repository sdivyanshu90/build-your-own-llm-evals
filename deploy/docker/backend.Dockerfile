FROM ghcr.io/astral-sh/uv:0.12.0 AS uv

FROM python:3.12.11-slim-bookworm AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY apps ./apps
COPY packages ./packages
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --reinstall-package llm-eval-platform

FROM python:3.12.11-slim-bookworm AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 eval \
    && useradd --uid 10001 --gid eval --no-create-home --shell /usr/sbin/nologin eval
WORKDIR /app
COPY --from=builder --chown=eval:eval /app/.venv /app/.venv
COPY --chown=eval:eval alembic.ini ./
COPY --chown=eval:eval uv.lock ./
COPY --chown=eval:eval migrations ./migrations
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "eval_platform_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
