"""API key authentication and rate limiting middleware."""

import logging
import secrets
import time
from typing import Optional

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60
# Raised from 120 -> 600 req/min: a V2 SPA session fans out to ~15 hooks
# at mount (signals, quota, me, portfolio, performance, agents…), each
# subscribing to AUTH_CHANGED_EVENT. A conservative upper bound needs to
# absorb the login burst + background refetches without tripping the
# limiter in dev. Re-tune once we move to per-user accounting.
RATE_LIMIT_MAX_REQUESTS = 600
PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json", "/ws/signals"}
PUBLIC_PREFIXES = ("/api/analytics/track-record",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per IP, backed by Redis.

    Pre-2026-04-27 (P1-2): kept the hit log in a per-process
    `defaultdict[str, list[float]]`. With N FastAPI workers each
    enforced its own 600/min counter, so the *effective* per-IP
    cluster limit was 600 × N — a hostile actor could trivially flood
    the cluster while every worker happily reported "below limit".

    This implementation stores each request as a member of a Redis
    sorted-set keyed `ratelimit:{ip}`; ZREMRANGEBYSCORE trims expired
    entries and ZCARD gives the live count. The four ops run inside
    one MULTI/EXEC pipeline so the count is consistent across all
    workers competing for the same IP.

    Failure mode: if Redis is unreachable we **fail open** (log + let
    the request through). A flaky cache must not turn into a global
    503 storm; over-permissive in a Redis blip is preferable to
    everyone getting a blank screen.
    """

    def __init__(self, app):
        super().__init__(app)
        self._redis = None  # lazily initialized

    async def _get_redis(self):
        # Lazy import + lazy connect so test code that swaps `redis_url`
        # before instantiating the app does not pin the URL at import.
        if self._redis is None:
            import redis.asyncio as aioredis  # type: ignore[import-not-found]
            settings = get_settings()
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        key = f"ratelimit:{client_ip}"
        # Unique sorted-set member — collision-free even when two requests
        # share the same `time.time()` (microsecond ties under load).
        member = f"{now}:{secrets.token_hex(4)}"

        try:
            redis_client = await self._get_redis()
            pipe = redis_client.pipeline(transaction=True)
            pipe.zadd(key, {member: now})
            pipe.zremrangebyscore(key, "-inf", now - RATE_LIMIT_WINDOW)
            pipe.zcard(key)
            pipe.expire(key, RATE_LIMIT_WINDOW + 1)
            results = await pipe.execute()
            count = int(results[2])
        except Exception:
            # Redis hiccup → fail open. Logging (not raising) is the right
            # call: a flaky cache must not turn into a global 503.
            logger.warning(
                "Rate limit Redis call failed for %s; allowing through",
                client_ip,
                exc_info=True,
            )
            return await call_next(request)

        if count > RATE_LIMIT_MAX_REQUESTS:
            logger.warning(
                "Rate limit exceeded for %s (count=%d, limit=%d)",
                client_ip,
                count,
                RATE_LIMIT_MAX_REQUESTS,
            )
            raise HTTPException(status_code=429, detail="Too many requests")

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, RATE_LIMIT_MAX_REQUESTS - count)
        )
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key gate. When SIGNAL_API_KEY is set, all non-public
    endpoints require `X-API-Key` header or `api_key` query param."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        required_key: Optional[str] = settings.signal_api_key

        if not required_key:
            return await call_next(request)

        path = request.url.path

        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        if not path.startswith("/api"):
            return await call_next(request)

        provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
        if provided != required_key:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        return await call_next(request)
