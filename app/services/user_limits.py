"""UserLimits service — age + cooloff gate + week_spent tracking.

Trading-test/quiz/budget gates were removed in favour of Apprendre as
the educational on-ramp; this module no longer touches OnboardingProgress
and only enforces age 18+ (captured at signup) plus auto-cooloff after
consecutive losses. Weekly budget tracking is preserved for analytics
but no longer caps trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from app.db.database import get_session_factory
from app.db.models import UserLimits

COOLOFF_HOURS = 24
COOLOFF_TRIGGER_LOSSES = 3


@dataclass
class TradeDecision:
    allowed: bool
    reason: Optional[str] = None
    remaining_budget_eur: Optional[float] = None


async def can_trade_real(user_id: int, stake_eur: float) -> TradeDecision:
    """Return whether this user may open a real-money trade of given stake.

    The L&T trading-test gates (tutorial, risk-quiz, weekly-budget setup)
    were removed in favour of Apprendre as the educational on-ramp. The
    only remaining hard gate is age 18+ — captured at signup, no separate
    page. Users who somehow land here without an age confirmation get
    blocked; everyone else is allowed.

    Cooloff (3 consecutive losses → 24h pause) is preserved as a
    self-protection mechanism: it triggers automatically based on
    outcomes and is independent of the deleted onboarding gates.
    """
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)

    # No row yet → user signed up after the gate-removal commit and never
    # touched the (now-deleted) budget page. Treat as allowed; the
    # signup-time age checkbox is our authority for the legal floor.
    if limits is None:
        return TradeDecision(allowed=True, remaining_budget_eur=None)

    if not limits.age_confirmed_18:
        return TradeDecision(allowed=False, reason="age_not_confirmed")

    now = datetime.now(timezone.utc)
    if limits.cooloff_until is not None and limits.cooloff_until > now:
        return TradeDecision(allowed=False, reason="in_cooloff")

    return TradeDecision(allowed=True, remaining_budget_eur=None)


async def register_trade_result(user_id: int, won: bool, stake_eur: float) -> None:
    """Call after outcome resolves. Updates consecutive_losses + triggers cooloff if needed."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return
        now = datetime.now(timezone.utc)
        # Treat missing week_reset_at as "just reset now" to avoid the None-check
        # footgun where fresh rows (server_default not yet populated) silently skip reset.
        week_reset_at = limits.week_reset_at or now
        if (now - week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = Decimal("0.00")
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
        # Treat missing week_reset_at as "just reset now" to avoid the None-check
        # footgun where fresh rows (server_default not yet populated) silently skip reset.
        week_reset_at = limits.week_reset_at or now
        if (now - week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = Decimal("0.00")
            limits.week_reset_at = now
        limits.week_spent_eur = Decimal(limits.week_spent_eur) + Decimal(str(stake_eur))
        limits.real_trades_count = (limits.real_trades_count or 0) + 1
        await s.commit()
