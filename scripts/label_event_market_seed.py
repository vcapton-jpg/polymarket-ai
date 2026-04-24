"""Human-review CLI for event→market ground-truth labels (chantier #4).

Two phases:
  1. sample — emit 500 (event_id, market_id) candidate pairs, stratified by
     bucket + rank bucket, to a staging JSONL.
  2. review — interactive terminal loop to accept/reject/edit each pair.

Usage:
    python -m scripts.label_event_market_seed sample --out docs/eval_labels/seed_candidates.jsonl
    python -m scripts.label_event_market_seed review \\
        --candidates docs/eval_labels/seed_candidates.jsonl \\
        --out docs/eval_labels/event_market_seed_2026-04-25.jsonl

The review phase is implemented in task 9. This task ships only `sample`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import random
import sys
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import Event, Market

logger = logging.getLogger(__name__)


BUCKETS = ("politics", "crypto", "sports", "tech", "other")
N_EVENTS_PER_BUCKET = 20
# From each event × top-20, we sample:
#   rank 1-3:   pick 1 per event  → ~ N_EVENTS (5×20 = 100)
#   rank 4-10:  pick 1 per event  → ~ 100
#   rank 11-20: pick 1 per event  → ~ 100
#   hors-top-20: pick 2 random markets in same bucket, not in top-20
#                                 → ~ 200
# Totals to ~500 candidates.
RANDOM_SEED = 42


async def _sample_events(session, bucket: str, n: int) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.bucket == bucket)
        .where(Event.embedding.isnot(None))
        .order_by(Event.last_seen.desc())
        .limit(n * 3)  # over-sample to allow filtering below
    )
    rows = (await session.execute(stmt)).scalars().all()
    return rows[:n]


async def _top20_for_event(session, event: Event) -> list[dict]:
    """Call the prod dispatcher (v1) to get top-20 candidates. We import
    here — not at module top — to avoid pulling Celery at script-parse time."""
    from app.retrieval import hybrid_search_markets
    emb = event.embedding
    if emb is None:
        return []
    text = event.event_retrieval_text or event.event_title
    return await hybrid_search_markets(
        session, list(emb), text, top_k=20,
        event_bucket=event.bucket, event_entities=event.key_entities,
        event_last_seen=event.last_seen,
    )


async def _random_out_of_top20(session, bucket: str, excluded: set[str], n: int) -> list[str]:
    stmt = (
        select(Market.market_id)
        .where(Market.bucket == bucket)
        .where(Market.active.is_(True))
        .where(Market.closed.is_(False))
    )
    rows = [r[0] for r in (await session.execute(stmt)).all() if r[0] not in excluded]
    rng = random.Random(RANDOM_SEED)
    rng.shuffle(rows)
    return rows[:n]


async def _cmd_sample(out_path: Path) -> int:
    factory = get_session_factory()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w") as f:
        async with factory() as session:
            for bucket in BUCKETS:
                events = await _sample_events(session, bucket, N_EVENTS_PER_BUCKET)
                if not events:
                    logger.warning("sample: bucket=%s has 0 events, skipping", bucket)
                    continue
                for ev in events:
                    candidates = await _top20_for_event(session, ev)
                    if not candidates:
                        continue
                    top20_ids = {c["market_id"] for c in candidates}
                    # Stratified pick from top-20.
                    slices = (
                        [c for c in candidates if 1 <= c.get("rank", 999) <= 3],
                        [c for c in candidates if 4 <= c.get("rank", 999) <= 10],
                        [c for c in candidates if 11 <= c.get("rank", 999) <= 20],
                    )
                    for sl in slices:
                        if sl:
                            pick = sl[0]
                            f.write(json.dumps({
                                "event_id": ev.id,
                                "market_id": pick["market_id"],
                                "event_title": ev.event_title,
                                "event_bucket": ev.bucket,
                                "market_question": pick.get("question"),
                                "rank_in_v1": pick.get("rank"),
                                "cosine_score": pick.get("cosine_score"),
                                "rrf_score": pick.get("rrf_score"),
                                "end_date": (
                                    pick.get("end_date").isoformat()
                                    if pick.get("end_date") else None
                                ),
                                "stratum": "top20",
                            }) + "\n")
                            written += 1
                    # Hors-top-20 random picks.
                    extras = await _random_out_of_top20(session, bucket, top20_ids, n=2)
                    for mid in extras:
                        mkt = (await session.execute(
                            select(Market).where(Market.market_id == mid)
                        )).scalar_one_or_none()
                        if mkt is None:
                            continue
                        f.write(json.dumps({
                            "event_id": ev.id,
                            "market_id": mid,
                            "event_title": ev.event_title,
                            "event_bucket": ev.bucket,
                            "market_question": mkt.question,
                            "rank_in_v1": None,
                            "cosine_score": None,
                            "rrf_score": None,
                            "end_date": mkt.end_date.isoformat() if mkt.end_date else None,
                            "stratum": "hors_top20",
                        }) + "\n")
                        written += 1
    logger.info("sample: wrote %d candidates → %s", written, out_path)
    return written


VALID_VERDICTS = {
    "s": "strong_match",
    "w": "weak_match",
    "n": "not_related",
}


def _cmd_review(candidates_path: Path, out_path: Path) -> int:
    """Interactive loop: read candidates JSONL, ask the user for each, write
    a labels JSONL idempotently. Resume-safe: if `out_path` already contains
    labels for a (event_id, market_id) pair, skip that candidate."""
    if not candidates_path.exists():
        print(f"error: candidates file not found: {candidates_path}")
        return 2
    out_path.parent.mkdir(parents=True, exist_ok=True)
    already: set[tuple[int, str]] = set()
    if out_path.exists():
        with out_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    already.add((int(row["event_id"]), str(row["market_id"])))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    print(f"resuming — {len(already)} pairs already labelled in {out_path}")

    with candidates_path.open() as src, out_path.open("a") as dst:
        todo = [json.loads(line) for line in src if line.strip()]
        total = len(todo)
        done = 0
        skipped = 0
        for i, cand in enumerate(todo, start=1):
            key = (int(cand["event_id"]), str(cand["market_id"]))
            if key in already:
                skipped += 1
                continue
            prompt = (
                f"[{i}/{total}] event: {cand.get('event_title')!r} (bucket={cand.get('event_bucket')})\n"
                f"         market: {cand.get('market_question')!r}\n"
                f"         cosine={cand.get('cosine_score')}, rank={cand.get('rank_in_v1')}, "
                f"stratum={cand.get('stratum')}, end_date={cand.get('end_date')}\n"
                "(s)trong / (w)eak / (n)ot_related / (k)skip / (q)uit&save > "
            )
            try:
                ans = input(prompt).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\naborted — partial progress saved.")
                break
            if ans == "q":
                break
            if ans == "k":
                continue
            verdict = VALID_VERDICTS.get(ans)
            if verdict is None:
                print(f"  unknown input {ans!r}, skipping")
                continue
            dst.write(json.dumps({
                "event_id": key[0],
                "market_id": key[1],
                "verdict": verdict,
                "source": "human",
            }) + "\n")
            dst.flush()
            done += 1
        print(f"done — labelled {done}, skipped {skipped}, remaining {total - done - skipped - len(already)}")
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="label_event_market_seed")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--out", required=True, type=Path)
    r = sub.add_parser("review")
    r.add_argument("--candidates", required=True, type=Path)
    r.add_argument("--out", required=True, type=Path)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    if args.cmd == "sample":
        n = asyncio.run(_cmd_sample(args.out))
        print(f"wrote {n} candidates to {args.out}")
        return 0
    if args.cmd == "review":
        return _cmd_review(args.candidates, args.out)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
