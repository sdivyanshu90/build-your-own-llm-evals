"""FastAPI composition root."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from eval_platform_domain.errors import DomainError, ErrorCode
from eval_platform_infrastructure.database import create_engine, create_session_factory
from eval_platform_infrastructure.logging import configure_logging
from eval_platform_infrastructure.object_store import S3ObjectStore
from eval_platform_infrastructure.observability import configure_tracing
from eval_platform_infrastructure.settings import Environment, Settings
from eval_platform_schemas.common import ErrorDetail, ErrorResponse
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from eval_platform_api.middleware import DistributedRateLimitMiddleware, RequestContextMiddleware
from eval_platform_api.routes import (
    access,
    analysis,
    datasets,
    experiments,
    health,
    metrics,
    projects,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create an application with explicitly composed infrastructure."""

    current = settings or Settings()
    current.validate_secure_runtime()
    configure_logging(
        current.log_level,
        json_output=current.environment is not Environment.DEVELOPMENT,
    )
    configure_tracing(
        "eval-platform-api",
        current.service_version,
        current.otlp_endpoint,
    )
    engine = create_engine(current.database_url.get_secret_value())
    object_store = S3ObjectStore(
        endpoint_url=current.s3_endpoint_url,
        region=current.s3_region,
        bucket=current.s3_bucket,
        access_key_id=current.s3_access_key_id.get_secret_value(),
        secret_access_key=current.s3_secret_access_key.get_secret_value(),
    )

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        try:
            if current.environment is Environment.DEVELOPMENT:
                await object_store.ensure_bucket()
            else:
                await object_store.check()
            yield
        finally:
            await engine.dispose()

    app = FastAPI(
        title="LLM Evaluation Platform API",
        version=current.service_version,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.state.settings = current
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    app.state.object_store = object_store
    if current.otlp_endpoint:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    app.add_middleware(
        DistributedRateLimitMiddleware,
        redis_url=current.redis_url.get_secret_value(),
        requests_per_minute=current.rate_limit_requests_per_minute,
        enabled=current.rate_limit_enabled,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=current.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "If-Match",
            "X-Organization-ID",
            "X-Project-ID",
            "X-Request-ID",
            "X-Role",
        ],
    )
    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(datasets.router)
    app.include_router(experiments.router)
    app.include_router(metrics.router)
    app.include_router(analysis.router)
    app.include_router(access.router)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        status_by_code = {
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.UNAUTHENTICATED: 401,
            ErrorCode.CONFLICT: 409,
            ErrorCode.IMMUTABLE: 409,
            ErrorCode.INVALID_STATE_TRANSITION: 409,
            ErrorCode.BUDGET_EXCEEDED: 422,
            ErrorCode.VALIDATION: 422,
        }
        body = ErrorResponse(
            error=error.code,
            message=error.message,
            request_id=request.state.request_id,
            details=[
                ErrorDetail(location=[key], message=str(value), code=error.code)
                for key, value in error.details.items()
            ],
        )
        return JSONResponse(
            status_code=status_by_code.get(error.code, 500),
            content=body.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorCode.VALIDATION,
            message="request validation failed",
            request_id=request.state.request_id,
            details=[
                ErrorDetail(
                    location=list(item["loc"]),
                    message=item["msg"],
                    code=item["type"],
                )
                for item in error.errors()
            ],
        )
        return JSONResponse(status_code=422, content=body.model_dump(mode="json"))

    @app.exception_handler(IntegrityError)
    async def integrity_error(request: Request, error: IntegrityError) -> JSONResponse:
        structlog.get_logger().warning(
            "database_integrity_error",
            request_id=request.state.request_id,
            error_type=type(error.orig).__name__,
        )
        body = ErrorResponse(
            error=ErrorCode.CONFLICT,
            message="resource conflicts with existing state",
            request_id=request.state.request_id,
        )
        return JSONResponse(status_code=409, content=body.model_dump(mode="json"))

    return app


app = create_app()
