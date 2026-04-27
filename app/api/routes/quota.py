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
from app.api.schemas.learn_and_trade import UserLimitsOut
from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import UserLimits, UserProfile

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


@router.get("/limits", response_model=UserLimitsOut)
async def get_my_limits(
    user: UserProfile = Depends(get_current_user),
) -> UserLimitsOut:
    """Authoritative Learn & Trade limits for the current user.

    Returns safe, locked defaults (age = False, cooloff = None) when no
    row exists — the frontend treats this as "not unlocked yet" rather
    than failing. Post-2026-04-27 the only fields the backend actually
    enforces are `age_confirmed_18` and `cooloff_until`; the legacy
    `budget_weekly_eur` / `max_stake_eur` / `quiz_passed` fields stay
    in the response shape for analytics back-compat but no longer cap
    trades. New users get a row on first real-trade attempt.
    """
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user.id)
    if limits is None:
        return UserLimitsOut(
            budget_weekly_eur=20.00,
            max_stake_eur=10.00,
            level=1,
            real_trades_count=0,
            consecutive_losses=0,
            week_spent_eur=0.00,
            cooloff_until=None,
            quiz_passed=False,
            age_confirmed_18=False,
        )
    return UserLimitsOut.model_validate(limits, from_attributes=True)
