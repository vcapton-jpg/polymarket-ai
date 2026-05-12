"""Shadow capture — record filter-rejected signals + label them.

T-ML in docs/PLAN_30D_SIGNAL_QUALITY.md. When T-001 or T-013 rejects a
candidate signal in `signal_builder.py`, we still want the price
trajectory it would have had so the future ML pipeline has labels for
the rejected cases. Without this, the model only learns from what the
filters already pass — survivor bias on every gradient step.

Two tasks live here:

* `record_shadow_signal(...)` — inserts one row in `shadow_signals`,
  then schedules four follow-up captures (5 min / 15 min / 1 h / 24 h).
  Called from `signal_builder.py:_log_shadow_rejection(...)` via
  `.delay(...)` so the rejection path stays sync-free.

* `capture_shadow_price(shadow_signal_id, market_id, field)` —
  mirror of `tasks_outcomes.capture_price` but writes to
  `shadow_signal_outcomes` instead of `signal_outcomes`. Idempotent on
  the (shadow_signal_id, field) tuple so a Celery retry can't double-
  write.

* `catchup_shadow_outcomes()` — beat-scheduled sibling of
  `catchup_outcomes`. Walks the last 48 h of `shadow_signals` and
  dispatches any missing capture for any field that is now eligible.

The capture cadence is identical to live signals so the two outcome
datasets can be joined / compared apples-to-apples downstream.

Feature-flagged behind `settings.enable_shadow_capture` (default OFF).
The Celery tasks themselves are unconditionally registered — only the
caller site in signal_builder gates the dispatch on the setting.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.workers._async_helpers import run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Capture cadence — mirror of tasks_outcomes for live signals.
# ──────────────────────────────────────────────────────────────────────
_FIELD_DELAY_SECONDS: dict[str, int] = {
    "price_t5min":  5  * 60,
    "price_t15min": 15 * 60,
    "price_t1h":    60 * 60,
    "price_t24h":   24 * 60 * 60,
}
_FIELD_MOVE_ATTR: dict[str, str] = {
    "price_t5min":  "move_t5min_pct",
    "price_t15min": "move_t15min_pct",
    "price_t1h":    "move_t1h_pct",
    "price_t24h":   "move_t24h_pct",
}


# ══════════════════════════════════════════════════════════════════════
# Recording — called from signal_builder when a filter rejects.
# ══════════════════════════════════════════════════════════════════════


@celery_app.task(name="app.workers.tasks_shadow.record_shadow_signal", bind=True, max_retries=2)
def record_shadow_signal(
    self,
    *,
    event_id: int | None,
    market_id: str,
    direction: str,
    market_price_at_signal: float,
    rejection_reason: str,
    llm_model_version: str | None = None,
    signal_score: float | None = None,
) -> dict:
    """Insert one shadow_signals row + schedule the 4 captures."""
    try:
        return run_async(_record_shadow_signal_async(
            event_id=event_id,
            market_id=market_id,
            direction=direction,
            market_price_at_signal=market_price_at_signal,
            rejection_reason=rejection_reason,
            llm_model_version=llm_model_version,
            signal_score=signal_score,
        ))
    except Exception as exc:
        logger.exception(
            "record_shadow_signal failed: market=%s reason=%s",
            market_id, rejection_reason,
        )
        raise self.retry(exc=exc, throw=False) from exc


async def _record_shadow_signal_async(
    *,
    event_id: int | None,
    market_id: str,
    direction: str,
    market_price_at_signal: float,
    rejection_reason: str,
    llm_model_version: str | None,
    signal_score: float | None,
) -> dict:
    from app.db.database import get_session_factory
    from app.db.models import ShadowSignal

    async_session_factory = get_session_factory()
    async with async_session_factory() as session:
        sig = ShadowSignal(
            event_id=event_id,
            market_id=market_id,
            direction=direction,
            market_price_at_signal=market_price_at_signal,
            rejection_reason=rejection_reason,
            llm_model_version=llm_model_version,
            signal_score=signal_score,
        )
        session.add(sig)
        await session.flush()
        shadow_signal_id = sig.id
        await session.commit()

    # Schedule the four price captures. We do this AFTER commit so the
    # row is visible to the capture task when it fires.
    for field, delay in _FIELD_DELAY_SECONDS.items():
        capture_shadow_price.apply_async(
            args=[shadow_signal_id, market_id, field],
            countdown=delay,
            queue="default",
        )

    logger.info(
        "shadow_signal recorded: id=%d market=%s direction=%s reason=%s",
        shadow_signal_id, market_id, direction, rejection_reason,
    )
    return {
        "status": "ok",
        "shadow_signal_id": shadow_signal_id,
        "captures_scheduled": list(_FIELD_DELAY_SECONDS.keys()),
    }


# ══════════════════════════════════════════════════════════════════════
# Capture — fired by the four countdowns above.
# ══════════════════════════════════════════════════════════════════════


@celery_app.task(
    name="app.workers.tasks_shadow.capture_shadow_price",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def capture_shadow_price(self, shadow_signal_id: int, market_id: str, field: str):
    """Capture the YES price for a shadow_signal at the given offset."""
    try:
        return run_async(_capture_shadow_price_async(shadow_signal_id, market_id, field))
    except Exception as exc:
        logger.exception(
            "capture_shadow_price failed: shadow_id=%d field=%s",
            shadow_signal_id, field,
        )
        raise self.retry(exc=exc, throw=False) from exc


async def _capture_shadow_price_async(
    shadow_signal_id: int, market_id: str, field: str
) -> dict:
    from sqlalchemy import select

    from app.db.database import get_session_factory
    from app.db.models import ShadowSignal, ShadowSignalOutcome
    from app.polymarket.clob_client import ClobClient

    if field not in _FIELD_MOVE_ATTR:
        return {"status": "bad_field", "field": field}

    clob = ClobClient()
    try:
        price = await clob.get_price_yes(market_id)
    finally:
        await clob.close()

    if price is None:
        return {"status": "no_price", "shadow_signal_id": shadow_signal_id, "field": field}

    async_session_factory = get_session_factory()
    async with async_session_factory() as session:
        outcome = (
            await session.execute(
                select(ShadowSignalOutcome).where(
                    ShadowSignalOutcome.shadow_signal_id == shadow_signal_id
                )
            )
        ).scalar_one_or_none()

        if outcome is None:
            outcome = ShadowSignalOutcome(shadow_signal_id=shadow_signal_id)
            session.add(outcome)

        # Idempotency — if this field is already populated, a retry must
        # not overwrite it with whatever the price is *now*.
        if getattr(outcome, field) is not None:
            return {
                "status": "already_captured",
                "shadow_signal_id": shadow_signal_id,
                "field": field,
                "price": float(getattr(outcome, field)),
            }

        setattr(outcome, field, price)

        # Compute move_*_pct against the base price snapshot.
        shadow = (
            await session.execute(
                select(ShadowSignal).where(ShadowSignal.id == shadow_signal_id)
            )
        ).scalar_one_or_none()
        if shadow and shadow.market_price_at_signal:
            base = float(shadow.market_price_at_signal)
            if base > 0:
                move_pct = ((price - base) / base) * 100
                setattr(outcome, _FIELD_MOVE_ATTR[field], round(move_pct, 4))

        await session.commit()

    logger.info(
        "capture_shadow_price: shadow_id=%d field=%s price=%.4f",
        shadow_signal_id, field, price,
    )
    return {
        "status": "ok",
        "shadow_signal_id": shadow_signal_id,
        "field": field,
        "price": price,
    }


# ══════════════════════════════════════════════════════════════════════
# Catch-up — fill missing snapshots for shadows the countdown missed.
# ══════════════════════════════════════════════════════════════════════


@celery_app.task(name="app.workers.tasks_shadow.catchup_shadow_outcomes", bind=True, max_retries=1)
def catchup_shadow_outcomes(self):
    try:
        return run_async(_catchup_shadow_outcomes_async())
    except Exception as exc:
        logger.exception("catchup_shadow_outcomes failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _catchup_shadow_outcomes_async() -> dict:
    from sqlalchemy import select

    from app.db.database import get_session_factory
    from app.db.models import ShadowSignal, ShadowSignalOutcome

    async_session_factory = get_session_factory()
    now = datetime.now(UTC)
    dispatched = 0

    async with async_session_factory() as session:
        # Limit to last 48 h — anything older is past the t+24h window.
        shadows = (
            await session.execute(
                select(ShadowSignal)
                .where(ShadowSignal.created_at >= now - timedelta(hours=48))
                .order_by(ShadowSignal.created_at.desc())
                .limit(200)
            )
        ).scalars().all()

        for sig in shadows:
            outcome = (
                await session.execute(
                    select(ShadowSignalOutcome).where(
                        ShadowSignalOutcome.shadow_signal_id == sig.id
                    )
                )
            ).scalar_one_or_none()

            age_min = (now - sig.created_at).total_seconds() / 60
            fields_to_capture: list[str] = []
            if age_min >= 5    and (not outcome or outcome.price_t5min  is None):
                fields_to_capture.append("price_t5min")
            if age_min >= 15   and (not outcome or outcome.price_t15min is None):
                fields_to_capture.append("price_t15min")
            if age_min >= 60   and (not outcome or outcome.price_t1h    is None):
                fields_to_capture.append("price_t1h")
            if age_min >= 1440 and (not outcome or outcome.price_t24h   is None):
                fields_to_capture.append("price_t24h")

            for field in fields_to_capture:
                capture_shadow_price.apply_async(
                    args=[sig.id, sig.market_id, field],
                    queue="default",
                )
                dispatched += 1

    logger.info("catchup_shadow_outcomes: dispatched %d price captures", dispatched)
    return {"status": "ok", "dispatched": dispatched}


__all__ = [
    "record_shadow_signal",
    "capture_shadow_price",
    "catchup_shadow_outcomes",
]
