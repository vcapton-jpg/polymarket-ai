"""Offline report over event_market_ranking_shadow rows (chantier #4).

Metrics:
  - total events with shadow coverage
  - divergence_rate_top1  — % events where rank-1 market differs between v1 and v2
  - divergence_top5_lt3    — % events where |top5_v1 ∩ top5_v2| < 3
  - per-bucket divergence
  - signal_delta_projection — for events that produced a prod signal, what
    would the v2 top-1 have surfaced? same / different market / neither.

Usage:
    python -m scripts.analyze_ranking_shadow --since 48h --out reports/shadow_2026-04-27.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event, EventMarketRankingShadow, Signal

logger = logging.getLogger(__name__)


async def _run(since: timedelta, out_path: Path) -> int:
    since_ts = datetime.now(UTC) - since
    factory = get_session_factory()
    async with factory() as session:
        # Fetch shadow rows and their matching prod ranks.
        shadow_rows = (await session.execute(
            select(EventMarketRankingShadow)
            .where(EventMarketRankingShadow.computed_at >= since_ts)
        )).scalars().all()
        if not shadow_rows:
            logger.info("no shadow rows since %s", since_ts)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps({"n_events": 0}, indent=2))
            return 0

        # Index shadow by (event_id, variant, rank).
        by_ev_variant: dict[int, dict[str, list[EventMarketRankingShadow]]] = {}
        for r in shadow_rows:
            by_ev_variant.setdefault(r.event_id, {}).setdefault(r.variant, []).append(r)

        # For the prod side, we need the prod top-5 at the time this event was
        # scored — that lives in `event_market_candidates` (v1 behaviour).
        # Here we use it implicitly: the shadow variant is the *opposite* of
        # prod, so per-event we have exactly one variant's shadow rows. To
        # compare, we need the prod ranking. Query `EventMarketCandidate`.
        from app.db.models import EventMarketCandidate
        prod_candidates = (await session.execute(
            select(EventMarketCandidate)
            .where(EventMarketCandidate.event_id.in_(by_ev_variant.keys()))
            .order_by(EventMarketCandidate.event_id, EventMarketCandidate.rank)
        )).scalars().all()
        prod_by_ev: dict[int, list[EventMarketCandidate]] = {}
        for c in prod_candidates:
            prod_by_ev.setdefault(c.event_id, []).append(c)

        # Events (for bucket stratification).
        events = (await session.execute(
            select(Event).where(Event.id.in_(by_ev_variant.keys()))
        )).scalars().all()
        event_bucket = {e.id: (e.bucket or "other") for e in events}

        # Prod signals — for signal-delta projection.
        signals = (await session.execute(
            select(Signal).where(Signal.event_id.in_(by_ev_variant.keys()))
        )).scalars().all()
        signal_market_by_ev: dict[int, str] = {s.event_id: s.market_id for s in signals}

    # Aggregate metrics.
    n_events = 0
    n_top1_diff = 0
    n_top5_low_overlap = 0
    bucket_stats: dict[str, dict[str, int]] = {}
    signal_delta = {"same": 0, "different": 0, "n_signals": 0}

    for eid, variants in by_ev_variant.items():
        # One shadow variant per event — pick it.
        shadow_variant, shadow_rows_e = next(iter(variants.items()))
        shadow_top = sorted(shadow_rows_e, key=lambda x: x.rank)
        prod_top = sorted(prod_by_ev.get(eid, []), key=lambda x: (x.rank or 99))
        if not prod_top:
            continue
        n_events += 1
        bucket = event_bucket.get(eid, "other")
        bucket_stats.setdefault(bucket, {"n": 0, "top1_diff": 0})
        bucket_stats[bucket]["n"] += 1

        shadow_top1 = shadow_top[0].market_id if shadow_top else None
        prod_top1 = prod_top[0].market_id if prod_top else None
        if shadow_top1 != prod_top1:
            n_top1_diff += 1
            bucket_stats[bucket]["top1_diff"] += 1

        shadow_top5 = {r.market_id for r in shadow_top[:5]}
        prod_top5 = {c.market_id for c in prod_top[:5]}
        if len(shadow_top5 & prod_top5) < 3:
            n_top5_low_overlap += 1

        if eid in signal_market_by_ev:
            signal_delta["n_signals"] += 1
            if signal_market_by_ev[eid] == shadow_top1:
                signal_delta["same"] += 1
            else:
                signal_delta["different"] += 1

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "since": since_ts.isoformat(),
        "n_events": n_events,
        "divergence_rate_top1": n_top1_diff / n_events if n_events else 0.0,
        "divergence_top5_lt3": n_top5_low_overlap / n_events if n_events else 0.0,
        "per_bucket": {
            b: {
                "n": st["n"],
                "top1_diff_rate": st["top1_diff"] / st["n"] if st["n"] else 0.0,
            }
            for b, st in bucket_stats.items()
        },
        "signal_delta_projection": signal_delta,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


def _parse_since(s: str) -> timedelta:
    s = s.strip().lower()
    if s.endswith("h"):
        return timedelta(hours=int(s[:-1]))
    if s.endswith("d"):
        return timedelta(days=int(s[:-1]))
    raise argparse.ArgumentTypeError("since must end in 'h' or 'd' (e.g. 48h, 7d)")


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="analyze_ranking_shadow")
    p.add_argument("--since", type=_parse_since, default=timedelta(hours=48))
    p.add_argument("--out", type=Path, default=Path("docs/eval_baselines/ranking_shadow_report.json"))
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(_run(args.since, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
