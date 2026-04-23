"""UserLimits service — enforces budget + cooloff + quiz gating on real trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits

COOLOFF_HOURS = 24
COOLOFF_TRIGGER_LOSSES = 3


@dataclass
class TradeDecision:
    allowed: bool
    reason: Optional[str] = None
    remaining_budget_eur: Optional[float] = None


async def can_trade_real(user_id: int, stake_eur: float) -> TradeDecision:
    """Return whether this user may open a real-money trade of given stake."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        onb = await s.get(OnboardingProgress, user_id)

    if limits is None:
        return TradeDecision(allowed=False, reason="no_limits_row")

    if not limits.age_confirmed_18:
        return TradeDecision(allowed=False, reason="age_not_confirmed")

    if onb is None or not onb.tutorial_done:
        return TradeDecision(allowed=False, reason="tutorial_not_done")

    if not limits.quiz_passed:
        return TradeDecision(allowed=False, reason="quiz_not_passed")

    if not onb.budget_done:
        return TradeDecision(allowed=False, reason="budget_not_set")

    now = datetime.now(timezone.utc)
    if limits.cooloff_until is not None and limits.cooloff_until > now:
        return TradeDecision(allowed=False, reason="in_cooloff")

    if stake_eur > float(limits.max_stake_eur):
        return TradeDecision(allowed=False, reason="over_max_stake")

    remaining = float(limits.budget_weekly_eur) - float(limits.week_spent_eur)
    if stake_eur > remaining:
        return TradeDecision(
            allowed=False, reason="over_weekly_budget", remaining_budget_eur=remaining
        )

    return TradeDecision(allowed=True, remaining_budget_eur=remaining - stake_eur)


async def register_trade_result(user_id: int, won: bool, stake_eur: float) -> None:
    """Call after outcome resolves. Updates consecutive_losses + triggers cooloff if needed."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return
        now = datetime.now(timezone.utc)
        if limits.week_reset_at is not None and (now - limits.week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = 0.00
            limits.week_reset_at = now

        if won:
            limits.consecutive_losses = 0
        else:
            limits.consecutive_losses = (limits.consecutive_losses or 0) + 1
            if limits.consecutive_losses >= COOLOFF_TRIGGER_LOSSES:
                limits.cooloff_until = now + timedelta(hours=COOLOFF_HOURS)

        await s.commit()


async def register_trade_opened(user_id: int, stake_eur: float) -> None:
    """Call when real trade placed. Debits weekly budget."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return
        now = datetime.now(timezone.utc)
        if limits.week_reset_at is not None and (now - limits.week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = 0.00
            limits.week_reset_at = now
        limits.week_spent_eur = float(limits.week_spent_eur) + stake_eur
        limits.real_trades_count = (limits.real_trades_count or 0) + 1
        await s.commit()
