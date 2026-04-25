"""Measurement pipeline — glue between signal persistence, baselines, and DB.

`record_baselines` runs inside the signal transaction (same session). It
inserts one row per registered baseline plus a 'heuristic_v1' row for the
frozen-reference prediction and (opt-in) a 'heuristic_shadow' row. Uses
ON CONFLICT DO NOTHING so a retry during backfill is safe.

`schedule_shadow_variants` enqueues the per-signal `sourcing_shadow_rerun`
Celery task (chantier #2).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Signal, SignalPrediction
from app.measurement.scoring_context import ScoringContext
from app.measurement.variant_registry import VariantRegistry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def record_baselines(
    session: "AsyncSession",
    *,
    signal_id: int,
    ctx: ScoringContext,
    registry: VariantRegistry,
    features: dict | None = None,
    llm_combined: float | None = None,
) -> int:
    """Insert one row per variant into signal_predictions.

    Variants written:
      - 'heuristic_v1' (frozen reference, always) — uses the Signal's own
        signal_strength/100 as probability, preserving pre-chantier #5
        bit-exactness.
      - 'heuristic_shadow' (optional, opt-in via
        settings.heuristic_shadow_enabled) — recomputed from the provided
        `features` + `llm_combined` under Settings-loaded weights. Skipped
        silently when `features is None` (defensive: the caller may forget
        to pass it for some legacy paths).
      - every baseline registered in `registry` — unchanged.

    Conflicts on (signal_id, variant) are swallowed via ON CONFLICT DO NOTHING
    so retries / backfills are idempotent.
    """
    from app.core.config import get_settings
    from app.measurement.heuristic_variant import predict_heuristic
    from app.scoring.weights import HeuristicWeights

    sig = (
        await session.execute(select(Signal).where(Signal.id == signal_id))
    ).scalar_one()
    signal_prob = (
        float(sig.signal_strength) / 100.0
        if sig.signal_strength is not None
        else 0.5
    )

    rows: list[dict] = [
        {
            "signal_id": signal_id,
            "variant": "heuristic_v1",
            "predicted_direction": sig.direction,
            "predicted_probability": signal_prob,
        }
    ]

    settings = get_settings()
    if settings.heuristic_shadow_enabled and features is not None:
        shadow_pred = predict_heuristic(
            weights=HeuristicWeights.load_from_settings(settings),
            features=features,
            llm_combined=llm_combined,
            direction=sig.direction,
        )
        rows.append(
            {
                "signal_id": signal_id,
                "variant": "heuristic_shadow",
                "predicted_direction": shadow_pred.direction,
                "predicted_probability": shadow_pred.probability,
            }
        )

    for name, fn in registry.baselines().items():
        pred = fn(ctx)
        rows.append(
            {
                "signal_id": signal_id,
                "variant": name,
                "predicted_direction": pred.direction,
                "predicted_probability": pred.probability,
            }
        )

    stmt = pg_insert(SignalPrediction).values(rows).on_conflict_do_nothing(
        index_elements=["signal_id", "variant"]
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def record_baselines_for_signal(
    session: "AsyncSession",
    *,
    signal: Signal,
    articles: list[dict] | None,
    market_price_24h_ago: float | None = None,
) -> int:
    """Production-path glue between a freshly flushed Signal and the
    measurement layer.

    Both the sync `tasks_scoring._run_full_scoring_pipeline` and the legacy
    async `signal_builder._persist_signal` call this so the wiring lives in
    one place. Pre-conditions:

      - `signal.id` is set (caller must `session.flush()` first).
      - `app.measurement` has been imported at least once so the four
        built-in baselines are registered.

    Reads `_features` / `_llm_combined` off the signal if the builder
    stashed them — they enable the optional `heuristic_shadow` row when
    Settings.heuristic_shadow_enabled is on. Both default to None for
    legacy callers.

    Wrapped in try/except: a measurement-layer failure must NOT abort the
    signal commit (the signal is already flushed and useful on its own).
    Returns the number of rows actually written, 0 on swallowed failure.
    """
    from app.measurement.scoring_context import build_scoring_context
    from app.measurement.variant_registry import get_registry

    try:
        ctx = await build_scoring_context(
            signal_id=signal.id,
            market_id=signal.market_id,
            event_id=signal.event_id,
            market_price=float(signal.market_price_at_signal or 0.0),
            articles=articles,
            t0=datetime.now(timezone.utc),
            market_price_24h_ago=market_price_24h_ago,
        )
        return await record_baselines(
            session,
            signal_id=signal.id,
            ctx=ctx,
            registry=get_registry(),
            features=getattr(signal, "_features", None),
            llm_combined=getattr(signal, "_llm_combined", None),
        )
    except Exception:
        logger.exception(
            "record_baselines_for_signal: failed signal_id=%s — skipping",
            signal.id,
        )
        return 0


def schedule_shadow_variants(signal_id: int) -> None:
    """Fire-and-forget shadow variant dispatch.

    Chantier #2: enqueues `sourcing_shadow_rerun` on the 'scoring' queue. The
    import is local so module load doesn't pull in Celery at API startup, and
    wrapped in a try/except so a broken broker never prevents a signal from
    committing.
    """
    try:
        from app.workers.tasks_sourcing import sourcing_shadow_rerun
        sourcing_shadow_rerun.delay(signal_id)
    except Exception:
        logger.exception(
            "schedule_shadow_variants: failed to enqueue signal_id=%s — continuing",
            signal_id,
        )


def _binary_from_resolved(price_resolved: float) -> int | None:
    if price_resolved >= 0.95:
        return 1
    if price_resolved <= 0.05:
        return 0
    return None


async def record_prediction_resolution(
    session: "AsyncSession",
    *,
    signal_id: int,
    price_resolved: float,
) -> int:
    """Fill direction_correct + brier + P&L + resolved_at for every variant
    of this signal that has a non-null direction and is still unresolved.

    Returns the count of rows updated. Idempotent (the WHERE clause skips rows
    that already have resolved_at set).
    """
    resolved_binary = _binary_from_resolved(price_resolved)
    expected_direction = "BUY_YES" if price_resolved >= 0.5 else "BUY_NO"
    now = datetime.now(timezone.utc)

    rows = (
        await session.execute(
            select(SignalPrediction).where(
                SignalPrediction.signal_id == signal_id,
                SignalPrediction.predicted_direction.is_not(None),
                SignalPrediction.resolved_at.is_(None),
            )
        )
    ).scalars().all()

    count = 0
    for r in rows:
        prob = float(r.predicted_probability) if r.predicted_probability is not None else 0.5
        r.direction_correct = (r.predicted_direction == expected_direction)
        r.brier_score = (
            None if resolved_binary is None else (prob - resolved_binary) ** 2
        )
        if r.predicted_direction == "BUY_YES":
            r.simulated_pnl_eur = 10.0 * (price_resolved - prob)
        else:  # BUY_NO
            r.simulated_pnl_eur = 10.0 * (prob - price_resolved)
        r.resolved_at = now
        count += 1
    return count
