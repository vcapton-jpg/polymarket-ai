"""Backfill signal_predictions for historical signals.

For every Signal row, insert the 5 variant rows (signal + 4 baselines). If the
signal's market already has a SignalOutcome.price_resolved value, compute
direction_correct / brier / pnl / resolved_at immediately.

Idempotent — ON CONFLICT DO NOTHING means rerunning is safe. `--since` limits
to recent signals. `--dry-run` reports intent without writing.

Usage:
    docker compose exec app python -m scripts.backfill_signal_predictions
    docker compose exec app python -m scripts.backfill_signal_predictions --dry-run
    docker compose exec app python -m scripts.backfill_signal_predictions --since 2026-04-01
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select

import app.measurement  # noqa: F401 — register baselines on import
from app.db.database import get_session_factory
from app.db.models import Signal, SignalOutcome, SignalPrediction
from app.measurement.pipeline import record_baselines, record_prediction_resolution
from app.measurement.scoring_context import build_scoring_context
from app.measurement.variant_registry import get_registry

logger = logging.getLogger(__name__)


async def backfill(
    *,
    dry_run: bool = False,
    since: datetime | None = None,
    batch_size: int = 100,
) -> dict:
    """Returns a stats dict including per-variant coverage counts."""
    factory = get_session_factory()
    registry = get_registry()

    stats = {
        "dry_run": dry_run,
        "signals_processed": 0,
        "predictions_inserted": 0,
        "resolutions_backfilled": 0,
        "coverage": defaultdict(int),
    }

    async with factory() as s:
        q = select(Signal).order_by(Signal.created_at)
        if since is not None:
            q = q.where(Signal.created_at >= since)
        signals = (await s.execute(q)).scalars().all()

    for batch_start in range(0, len(signals), batch_size):
        batch = signals[batch_start : batch_start + batch_size]
        async with factory() as s:
            for sig in batch:
                stats["signals_processed"] += 1

                ctx = await build_scoring_context(
                    signal_id=sig.id,
                    market_id=sig.market_id,
                    event_id=sig.event_id,
                    market_price=float(sig.market_price_at_signal or 0.5),
                    articles=None,  # historical articles not reconstructed
                    t0=sig.created_at or datetime.now(timezone.utc),
                    market_price_24h_ago=None,  # no price history at backfill time
                )

                if dry_run:
                    for name in ("signal",) + tuple(registry.baselines().keys()):
                        stats["coverage"][name] += 1
                    continue

                inserted = await record_baselines(
                    s, signal_id=sig.id, ctx=ctx, registry=registry
                )
                stats["predictions_inserted"] += inserted
                for name in ("signal",) + tuple(registry.baselines().keys()):
                    stats["coverage"][name] += 1

                outcome = (
                    await s.execute(
                        select(SignalOutcome).where(SignalOutcome.signal_id == sig.id)
                    )
                ).scalar_one_or_none()
                if outcome is not None and outcome.price_resolved is not None:
                    n = await record_prediction_resolution(
                        s, signal_id=sig.id, price_resolved=float(outcome.price_resolved)
                    )
                    stats["resolutions_backfilled"] += n

            if not dry_run:
                await s.commit()

    # Coverage report
    print(f"Processed: {stats['signals_processed']} signals")
    print("Coverage by variant:")
    total = max(stats["signals_processed"], 1)
    for name, count in sorted(stats["coverage"].items()):
        pct = 100.0 * count / total
        print(f"  {name:26} → {count:5} ({pct:5.1f}%)")
    print(f"Outcomes backfilled: {stats['resolutions_backfilled']} rows updated")
    if dry_run:
        print("(dry-run: no rows written)")

    stats["coverage"] = dict(stats["coverage"])
    return stats


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--since", type=str, default=None, help="YYYY-MM-DD")
    p.add_argument("--batch-size", type=int, default=100)
    return p.parse_args(argv)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args()
    since = None
    if args.since:
        since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    asyncio.run(backfill(dry_run=args.dry_run, since=since, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
