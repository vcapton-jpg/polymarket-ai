"""API key authentication and rate limiting middleware."""

import logging
import time
from collections import defaultdict

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 120
PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json", "/ws/signals"}
PUBLIC_PREFIXES = ("/api/analytics/track-record",)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter per IP."""

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        window = self._hits[client_ip]
        window[:] = [t for t in window if now - t < RATE_LIMIT_WINDOW]

        if len(window) >= RATE_LIMIT_MAX_REQUESTS:
            logger.warning("Rate limit exceeded for %s", client_ip)
            raise HTTPException(status_code=429, detail="Too many requests")

        window.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(RATE_LIMIT_MAX_REQUESTS - len(window))
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Optional API key gate. When SIGNAL_API_KEY is set, all non-public
    endpoints require `X-API-Key` header or `api_key` query param."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        required_key = settings.signal_api_key

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
