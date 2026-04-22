"""Daily signal view quota — server-side ground truth for Free-plan gating.

Keys live in Redis under `quota:{user_id}:{YYYY-MM-DD}` with TTL = 2 days so
old counters expire without manual cleanup. Pro users always get `limit=-1`
(unlimited) — the client respects this and disables the paywall UI.

The client (`frontend/src/lib/dailyLimit.ts`) maintains a local mirror for
optimistic updates. The mirror is reconciled on mount + on `consume`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.models import UserProfile


router = APIRouter(prefix="/me", tags=["me"])

FREE_DAILY_LIMIT = 5


def _today_key(user_id: int) -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    return f"quota:{user_id}:{day}"


def _ttl_seconds() -> int:
    # 48h: covers rollover across timezones without ever losing the current
    # day's counter to an early TTL.
    return 2 * 24 * 3600


_redis_client: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


def _next_reset_iso() -> str:
    """00:00 UTC tomorrow — matches the server's day boundary."""
    now = datetime.now(timezone.utc)
    tomorrow = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return tomorrow.isoformat()


class QuotaOut(BaseModel):
    used: int
    limit: int
    resets_at: str


@router.get("/quota", response_model=QuotaOut)
async def get_quota(user: UserProfile = Depends(get_current_user)) -> QuotaOut:
    if user.plan == "pro":
        return QuotaOut(used=0, limit=-1, resets_at=_next_reset_iso())
    r = await _get_redis()
    raw = await r.get(_today_key(user.id))
    used = int(raw) if raw else 0
    return QuotaOut(used=used, limit=FREE_DAILY_LIMIT, resets_at=_next_reset_iso())


@router.post("/quota/consume", response_model=QuotaOut)
async def consume_quota(user: UserProfile = Depends(get_current_user)) -> QuotaOut:
    """Increment the Free-plan counter by one. Pro users are a no-op."""
    if user.plan == "pro":
        return QuotaOut(used=0, limit=-1, resets_at=_next_reset_iso())
    r = await _get_redis()
    key = _today_key(user.id)
    used = await r.incr(key)
    # Only set TTL on first write of the day. INCR doesn't reset it.
    if used == 1:
        await r.expire(key, _ttl_seconds())
    return QuotaOut(
        used=int(used),
        limit=FREE_DAILY_LIMIT,
        resets_at=_next_reset_iso(),
    )
