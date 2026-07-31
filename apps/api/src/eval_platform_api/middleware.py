"""Request correlation, metrics, and security-header middleware."""

from __future__ import annotations

import hashlib
import re
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from eval_platform_infrastructure.observability import HTTP_DURATION, HTTP_REQUESTS
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a safe request ID and emit bounded-cardinality request telemetry."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        supplied = request.headers.get("X-Request-ID", "")
        request_id = supplied if _REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        elapsed = time.perf_counter() - started
        HTTP_REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, route).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response


class DistributedRateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed fixed-window protection shared by every API replica."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        redis_url: str,
        requests_per_minute: int,
        enabled: bool,
    ) -> None:
        super().__init__(app)
        self._enabled = enabled
        self._limit = requests_per_minute
        self._redis = Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled or request.url.path in {
            "/health/live",
            "/health/ready",
            "/metrics",
        }:
            return await call_next(request)
        identity = request.headers.get("Authorization") or (
            request.client.host if request.client else "unknown"
        )
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        window = int(time.time() // 60)
        key = f"rate:v1:{digest}:{window}"
        try:
            count = int(await self._redis.incr(key))
            if count == 1:
                await self._redis.expire(key, 65)
        except RedisError:
            return JSONResponse(
                status_code=503,
                content={
                    "error": "dependency_unavailable",
                    "message": "rate-limit coordination is unavailable",
                    "request_id": getattr(request.state, "request_id", "unavailable"),
                    "details": [],
                },
                headers={"Retry-After": "5"},
            )
        if count > self._limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "request rate limit exceeded",
                    "request_id": getattr(request.state, "request_id", "unavailable"),
                    "details": [],
                },
                headers={
                    "Retry-After": str(60 - int(time.time()) % 60),
                    "X-RateLimit-Limit": str(self._limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self._limit - count))
        return response
