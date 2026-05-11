"""UserLimits service — age + cooloff gate.

Trading-test/quiz/budget gates were removed (DEC-007) in favour of
Apprendre as the educational on-ramp; this module no longer touches
OnboardingProgress and only enforces age 18+ (captured at signup) plus
auto-cooloff after consecutive losses.

The legacy `week_spent_eur` / `real_trades_count` writes were removed
2026-04-27 (P1-12) — they had no consumers (frontend reads neither, no
analytics dashboard consumes them) so the writes were pure dead I/O on
the trading hot path. The columns remain on `user_limits` for back-
compat with the `/me/limits` response shape; future cleanup can drop
the columns entirely.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.db.database import get_session_factory
from app.db.models import UserLimits

COOLOFF_HOURS = 24
COOLOFF_TRIGGER_LOSSES = 3


@dataclass
class TradeDecision:
    allowed: bool
    reason: str | None = None
    remaining_budget_eur: float | None = None


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

    now = datetime.now(UTC)
    if limits.cooloff_until is not None and limits.cooloff_until > now:
        return TradeDecision(allowed=False, reason="in_cooloff")

    return TradeDecision(allowed=True, remaining_budget_eur=None)


async def register_trade_result(user_id: int, won: bool, stake_eur: float) -> None:
    """Call after outcome resolves. Updates consecutive_losses + triggers cooloff if needed.

    `stake_eur` is kept in the signature for caller back-compat but is no
    longer used — the weekly-budget reset block was removed (P1-12) since
    `week_spent_eur` has no consumers. The cooloff side-effect (3 losses
    in a row → 24h pause) is the only behavior that remains.
    """
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return
        now = datetime.now(UTC)

        if won:
            limits.consecutive_losses = 0
        else:
            limits.consecutive_losses = (limits.consecutive_losses or 0) + 1
            if limits.consecutive_losses >= COOLOFF_TRIGGER_LOSSES:
                limits.cooloff_until = now + timedelta(hours=COOLOFF_HOURS)

        await s.commit()


async def register_trade_opened(user_id: int, stake_eur: float) -> None:
    """No-op since 2026-04-27 (P1-12).

    Previously debited `week_spent_eur` and incremented `real_trades_count`,
    but neither field is read by any consumer post-DEC-007. Kept as a stub
    so callers in `app/api/routes/trading.py` and tests don't have to
    change in this PR; a follow-up can drop the function + its callers.
    """
    return None
