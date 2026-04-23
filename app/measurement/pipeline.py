"""Measurement pipeline — glue between signal persistence, baselines, and DB.

`record_baselines` runs inside the signal transaction (same session). It
inserts one row per registered baseline plus one 'signal' row for the
production prediction. Uses ON CONFLICT DO NOTHING so a retry during backfill
is safe.

`schedule_shadow_variants` is a stub — chantiers #3/#4 will register shadow
variants that run async via Celery.
"""

from __future__ import annotations

import logging
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
) -> int:
    """Insert one row for the 'signal' variant + one per registered baseline.

    Caller is responsible for committing. Conflicts on (signal_id, variant)
    are swallowed silently — backfill retries are idempotent.
    """
    sig = (
        await session.execute(select(Signal).where(Signal.id == signal_id))
    ).scalar_one()
    signal_prob = (
        float(sig.signal_strength) / 100.0
        if sig.signal_strength is not None
        else 0.5
    )

    rows = [
        {
            "signal_id": signal_id,
            "variant": "signal",
            "predicted_direction": sig.direction,
            "predicted_probability": signal_prob,
        }
    ]
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


def schedule_shadow_variants(signal_id: int) -> None:
    """Fire-and-forget shadow variant dispatch. Stub until chantier #3."""
    logger.debug("schedule_shadow_variants(signal_id=%s) — no shadows registered", signal_id)
