"""Celery tasks — outcome capture (delayed price snapshots + resolution).

Phase 7: capture_price, check_resolved_markets
"""

import asyncio
import logging

from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════
# Capture price at T+offset
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def capture_price(self, signal_id: int, market_id: str, field: str):
    """Capture market price at T+offset and write to signal_outcomes.

    `field` is one of: price_t5min, price_t15min, price_t1h, price_t24h.
    """
    try:
        return _run_async(_capture_price_async(signal_id, market_id, field))
    except Exception as exc:
        logger.exception("capture_price failed: signal=%s field=%s", signal_id, field)
        raise self.retry(exc=exc)


async def _capture_price_async(signal_id: int, market_id: str, field: str) -> dict:
    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Signal, SignalOutcome
    from app.polymarket.clob_client import ClobClient

    valid_fields = {"price_t5min", "price_t15min", "price_t1h", "price_t24h"}
    if field not in valid_fields:
        return {"status": "invalid_field", "field": field}

    clob = ClobClient()
    try:
        price = await clob.get_price_yes(market_id)
    except Exception as e:
        logger.warning("Could not fetch price for %s: %s", market_id, e)
        return {"status": "price_fetch_failed"}
    finally:
        await clob.close()

    if price is None:
        return {"status": "no_price", "market_id": market_id}

    async with async_session_factory() as session:
        outcome = (
            await session.execute(
                select(SignalOutcome).where(SignalOutcome.signal_id == signal_id)
            )
        ).scalar_one_or_none()

        if not outcome:
            outcome = SignalOutcome(signal_id=signal_id)
            session.add(outcome)

        setattr(outcome, field, price)

        signal = (
            await session.execute(
                select(Signal).where(Signal.id == signal_id)
            )
        ).scalar_one_or_none()

        move_attr = {
            "price_t5min": "move_t5min_pct",
            "price_t15min": "move_t15min_pct",
            "price_t1h": "move_t1h_pct",
            "price_t24h": "move_t24h_pct",
        }.get(field)

        if signal and signal.market_price_at_signal and move_attr:
            base = float(signal.market_price_at_signal)
            if base > 0:
                move_pct = ((price - base) / base) * 100
                setattr(outcome, move_attr, round(move_pct, 4))

        await session.commit()

    logger.info("capture_price: signal=%d field=%s price=%.4f", signal_id, field, price)
    return {"status": "ok", "signal_id": signal_id, "field": field, "price": price}


# ══════════════════════════════════════════════════════════════════════════
# Catch-up — fill missing price snapshots for signals that were missed
# (worker restart, task timeout, etc.)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def catchup_outcomes(self):
    """Find signals with missing price fields and dispatch capture_price now."""
    try:
        return _run_async(_catchup_outcomes_async())
    except Exception as exc:
        logger.exception("catchup_outcomes failed")
        raise self.retry(exc=exc)


async def _catchup_outcomes_async() -> dict:
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Signal, SignalOutcome

    now = datetime.now(timezone.utc)
    dispatched = 0

    async with async_session_factory() as session:
        signals = (
            await session.execute(
                select(Signal)
                .outerjoin(SignalOutcome)
                .where(Signal.created_at >= now - timedelta(hours=48))
                .order_by(Signal.created_at.desc())
                .limit(50)
            )
        ).scalars().all()

        for sig in signals:
            outcome = (
                await session.execute(
                    select(SignalOutcome).where(SignalOutcome.signal_id == sig.id)
                )
            ).scalar_one_or_none()

            age = now - sig.created_at
            age_min = age.total_seconds() / 60

            fields_to_capture = []
            if age_min >= 5 and (not outcome or outcome.price_t5min is None):
                fields_to_capture.append("price_t5min")
            if age_min >= 15 and (not outcome or outcome.price_t15min is None):
                fields_to_capture.append("price_t15min")
            if age_min >= 60 and (not outcome or outcome.price_t1h is None):
                fields_to_capture.append("price_t1h")
            if age_min >= 1440 and (not outcome or outcome.price_t24h is None):
                fields_to_capture.append("price_t24h")

            for field in fields_to_capture:
                capture_price.apply_async(
                    args=[sig.id, sig.market_id, field],
                    queue="default",
                )
                dispatched += 1

    logger.info("catchup_outcomes: dispatched %d price captures", dispatched)
    return {"status": "ok", "dispatched": dispatched}


# ══════════════════════════════════════════════════════════════════════════
# Check resolved markets — daily job
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def check_resolved_markets(self):
    """Poll resolved markets and fill price_resolved + outcome_label + direction_correct."""
    try:
        return _run_async(_check_resolved_async())
    except Exception as exc:
        logger.exception("check_resolved_markets failed")
        raise self.retry(exc=exc)


async def _check_resolved_async() -> dict:
    from sqlalchemy import select

    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Market, Signal, SignalOutcome
    from app.polymarket.gamma_client import GammaClient

    gamma = GammaClient()

    try:
        async with async_session_factory() as session:
            signals_without_resolution = (
                await session.execute(
                    select(Signal)
                    .outerjoin(SignalOutcome)
                    .where(
                        (SignalOutcome.price_resolved.is_(None))
                        | (SignalOutcome.signal_id.is_(None))
                    )
                    .limit(100)
                )
            ).scalars().all()

            if not signals_without_resolution:
                return {"status": "nothing_to_check"}

            market_ids = list({s.market_id for s in signals_without_resolution})
            fresh_status = await _fetch_market_status_from_gamma(gamma, market_ids)

            resolved = 0
            updated_markets = 0
            for signal in signals_without_resolution:
                market = (
                    await session.execute(
                        select(Market).where(Market.market_id == signal.market_id)
                    )
                ).scalar_one_or_none()

                if not market:
                    continue

                gamma_data = fresh_status.get(signal.market_id)
                if gamma_data:
                    if gamma_data.get("closed") and not market.closed:
                        market.closed = True
                        market.active = False
                        if gamma_data.get("last_trade_price") is not None:
                            market.last_trade_price = gamma_data["last_trade_price"]
                        updated_markets += 1

                if not market.closed:
                    continue

                final_price = float(market.last_trade_price) if market.last_trade_price else None
                if final_price is None:
                    continue

                outcome = (
                    await session.execute(
                        select(SignalOutcome).where(SignalOutcome.signal_id == signal.id)
                    )
                ).scalar_one_or_none()

                if not outcome:
                    outcome = SignalOutcome(signal_id=signal.id)
                    session.add(outcome)

                outcome.price_resolved = final_price

                if signal.market_price_at_signal is not None:
                    from app.signal.direction_eval import direction_matches_price_move

                    base = float(signal.market_price_at_signal)
                    outcome.direction_correct = direction_matches_price_move(
                        signal.direction or "",
                        base,
                        float(final_price),
                    )

                if final_price >= 0.95:
                    outcome.outcome_label = 1
                elif final_price <= 0.05:
                    outcome.outcome_label = 0
                else:
                    outcome.outcome_label = None

                resolved += 1

            await session.commit()

        logger.info(
            "check_resolved_markets: resolved=%d signals, updated=%d markets from Gamma",
            resolved, updated_markets,
        )
        return {"status": "ok", "resolved": resolved, "markets_updated": updated_markets}

    finally:
        await gamma.close()


async def _fetch_market_status_from_gamma(gamma, market_ids: list[str]) -> dict:
    """Re-fetch market status from Gamma API to detect closures missed by local state."""
    result = {}
    for mid in market_ids:
        try:
            data = await gamma._get("/markets", params={"id": mid})
            items = data if isinstance(data, list) else [data]
            for item in items:
                cid = item.get("conditionId") or item.get("condition_id")
                if cid == mid or not cid:
                    result[mid] = {
                        "closed": item.get("closed", False),
                        "active": item.get("active", True),
                        "last_trade_price": _safe_float(item.get("lastTradePrice")),
                    }
                    break
        except Exception:
            logger.debug("Gamma re-fetch failed for market %s", mid, exc_info=True)
    return result


def _safe_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ── Task 8: Cooloff trigger hook ─────────────────────────────────────────
from app.services.user_limits import register_trade_result  # noqa: E402


async def register_user_outcome_for_signal(
    user_id: int, won: bool, stake_eur: float
) -> None:
    """Call once per user who had a real position on a resolved signal.

    Delegates to the UserLimits service to update consecutive_losses and
    trigger cooloff when the 3-loss threshold is hit.

    NOTE: wiring from ``check_resolved_markets()`` to this hook is deferred
    until the positions→signal mapping is in place (see plan Task 13 and the
    comment in the plan's Task 8 step 3). This function is already safe to
    call once that mapping lands.
    """
    await register_trade_result(user_id=user_id, won=won, stake_eur=stake_eur)
