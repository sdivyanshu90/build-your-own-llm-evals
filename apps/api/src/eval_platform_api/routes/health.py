"""Liveness, readiness, and metrics endpoints."""

from __future__ import annotations

from typing import cast

from eval_platform_infrastructure.object_store import ObjectStore, ObjectStoreError
from fastapi import APIRouter, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from eval_platform_api.dependencies import SessionDependency

router = APIRouter(tags=["operations"])


@router.get("/health/live")
async def liveness() -> dict[str, str]:
    """Report that the process event loop is responsive."""

    return {"status": "alive"}


@router.get("/health/ready")
async def readiness(request: Request, session: SessionDependency) -> dict[str, str]:
    """Require database, Redis coordination, and object storage."""

    settings = request.app.state.settings
    redis = Redis.from_url(
        settings.redis_url.get_secret_value(),
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    try:
        await session.execute(text("SELECT 1"))
        await redis.ping()
        await cast(ObjectStore, request.app.state.object_store).check()
    except (SQLAlchemyError, RedisError, ObjectStoreError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="required dependency is unavailable",
        ) from error
    finally:
        await redis.aclose()
    return {"status": "ready", "database": "ready", "redis": "ready", "object_store": "ready"}


@router.get("/metrics", response_class=Response)
async def metrics() -> Response:
    """Expose Prometheus text-format metrics."""

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
        status_code=status.HTTP_200_OK,
    )
