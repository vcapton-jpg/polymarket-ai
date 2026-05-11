"""Offline replay — compare ImpactAnalyzer v1 vs v2 on real prod events.

T-009 in docs/PLAN_30D_SIGNAL_QUALITY.md. Plan §6 rule:

> Tu décides de flipper le toggle prompt v1→v2 SEULEMENT après avoir
> lancé ce script, lu le rapport, et constaté que l'agrément v1↔v2
> est cohérent (typiquement ≥ 70 %) ET que les désaccords sont
> directionnellement profitables (v2 propose souvent NEUTRAL là où
> v1 sur-confidence un BUY_NO sur extrême prix).

USAGE
-----
Run from the VPS where the API container has DB + OpenAI access:

    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T app python -m scripts.shadow.compare_impact_v1_v2 \\
      --sample-size 50 --window-days 14'

The script reads the last N persisted `event_market_analysis` rows
(joined with their event + market for price), re-runs the v2 prompt
on each one, and emits a markdown report with:
  * Agreement rate (direction match) overall + by price bucket
  * Distribution of disagreements (e.g. "v1 BUY_NO → v2 NEUTRAL" count)
  * Token cost of the replay so you know what the next deployment costs

The script is **read-only** w.r.t. the production DB — it only does
SELECTs. The LLM calls are real spend on the operator's OpenAI key
(~$0.001 per pair at gpt-4o-mini rates, so a 50-event run is ~$0.05).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# Repo root on path so `from app.* import ...` works as a CLI module.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


async def _fetch_recent_analyses(window_days: int, sample_size: int) -> list[dict]:
    """Pull recent `event_market_analysis` rows with the matching event
    text + market question + price. Newest first, capped at `sample_size`."""
    from sqlalchemy import text

    from app.db.database import get_session_factory

    sql = text(
        f"""
        SELECT
            ema.event_id,
            ema.market_id,
            ema.impact_direction        AS v1_direction,
            ema.impact_strength         AS v1_strength,
            ema.llm_confidence          AS v1_confidence,
            ema.specificity_score       AS v1_specificity,
            ema.llm_model_version       AS v1_model,
            ema.created_at              AS v1_ts,
            e.event_title,
            e.event_summary,
            m.question                  AS market_question,
            m.last_trade_price          AS market_yes_price
        FROM event_market_analysis ema
        JOIN events e ON e.id = ema.event_id
        JOIN markets m ON m.market_id = ema.market_id
        WHERE ema.created_at > NOW() - INTERVAL '{int(window_days)} days'
          AND m.last_trade_price IS NOT NULL
          AND ema.impact_direction IS NOT NULL
        ORDER BY ema.created_at DESC
        LIMIT {int(sample_size)}
        """
    )

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        rows = (await session.execute(sql)).mappings().all()

    return [dict(r) for r in rows]


async def _replay_one(row: dict) -> dict:
    """Re-run v2 on one row. Returns the merged dict (v1 + v2 fields)."""
    # Force a fresh v2 analyzer — don't touch the cached singleton
    # because the operator may still be on v1 in `.env`.
    from app.core.config import get_settings
    from app.llm.impact_analyzer import ImpactAnalyzer

    original_version = get_settings().impact_prompt_version
    settings = get_settings()
    settings.impact_prompt_version = "v2"
    try:
        v2 = ImpactAnalyzer()
    finally:
        settings.impact_prompt_version = original_version

    event_text = f"{row['event_title']}. {row['event_summary'] or ''}"
    v2_result = await v2.analyze(
        event_text,
        row["market_question"],
        market_yes_price=float(row["market_yes_price"]),
    )

    merged = {
        "event_id": row["event_id"],
        "market_id": row["market_id"],
        "market_yes_price": float(row["market_yes_price"]),
        "v1_direction": row["v1_direction"],
        "v1_strength": float(row["v1_strength"]) if row["v1_strength"] is not None else None,
        "v1_confidence": float(row["v1_confidence"]) if row["v1_confidence"] is not None else None,
        "v2_direction": None,
        "v2_strength": None,
        "v2_confidence": None,
        "v2_implied_yes": None,
        "v2_reasoning": None,
        "agreement": False,
    }
    if v2_result:
        merged.update(
            {
                "v2_direction": (v2_result.get("impact_direction") or v2_result.get("direction") or "").upper() or None,
                "v2_strength": v2_result.get("impact_strength") or v2_result.get("impact_score"),
                "v2_confidence": v2_result.get("llm_confidence") or v2_result.get("confidence"),
                "v2_implied_yes": v2_result.get("implied_yes_probability"),
                "v2_reasoning": v2_result.get("reasoning"),
            }
        )
        merged["agreement"] = _normalize_direction(merged["v1_direction"]) == _normalize_direction(merged["v2_direction"])
    return merged


def _normalize_direction(d: Any) -> str:
    """BUY_YES/YES/UP → YES, BUY_NO/NO/DOWN → NO, else as-is."""
    if d is None:
        return ""
    s = str(d).upper()
    if s in ("BUY_YES", "YES", "UP"):
        return "YES"
    if s in ("BUY_NO", "NO", "DOWN"):
        return "NO"
    return s


def _price_bucket(p: float) -> str:
    if p < 0.20:
        return "YES<0.20 (deep-NO)"
    if p < 0.40:
        return "YES 0.20-0.40"
    if p < 0.60:
        return "YES 0.40-0.60 (mid)"
    if p < 0.80:
        return "YES 0.60-0.80"
    return "YES≥0.80 (deep-YES)"


def _emit_markdown_report(results: list[dict]) -> None:
    n = len(results)
    if n == 0:
        print("# No rows to compare.")
        return

    agreement_n = sum(1 for r in results if r["agreement"])
    print(f"# v1 vs v2 ImpactAnalyzer — n={n}")
    print()
    print(f"**Agreement rate (normalized direction):** {agreement_n}/{n} = {100*agreement_n/n:.1f} %")
    print()

    # Agreement by price bucket — this is where the value is. If v2
    # specifically disagrees on extreme prices (where T-001 fires too),
    # it's directly attacking the same toxic zone.
    print("## Agreement by market YES price bucket")
    print()
    print("| price bucket | n | agreement | disagreement detail |")
    print("|---|---:|---:|---|")
    by_bucket: dict[str, list[dict]] = {}
    for r in results:
        by_bucket.setdefault(_price_bucket(r["market_yes_price"]), []).append(r)
    for bucket in sorted(by_bucket.keys()):
        rows = by_bucket[bucket]
        agree = sum(1 for r in rows if r["agreement"])
        disagree_counter = Counter(
            f"{_normalize_direction(r['v1_direction'])}→{_normalize_direction(r['v2_direction'])}"
            for r in rows
            if not r["agreement"]
        )
        disagree_str = ", ".join(f"{k}: {v}" for k, v in disagree_counter.most_common(3)) or "—"
        print(f"| {bucket} | {len(rows)} | {agree}/{len(rows)} = {100*agree/len(rows):.0f} % | {disagree_str} |")
    print()

    # Top disagreements as worked examples — operator skim to gut-check
    # whether v2 is being smart or pathological.
    print("## Disagreement examples (up to 5)")
    print()
    disagreements = [r for r in results if not r["agreement"]][:5]
    for r in disagreements:
        print(f"- **event {r['event_id']} × market {r['market_id'][:16]}** "
              f"(YES={r['market_yes_price']:.3f})")
        print(f"  - v1: {r['v1_direction']} (strength={r['v1_strength']}, conf={r['v1_confidence']})")
        print(f"  - v2: {r['v2_direction']} (strength={r['v2_strength']}, conf={r['v2_confidence']}, "
              f"implied_yes={r['v2_implied_yes']})")
        if r["v2_reasoning"]:
            print(f"  - v2 reasoning: _{r['v2_reasoning']}_")
        print()


async def main_async(window_days: int, sample_size: int, json_out: str | None) -> int:
    print(f"Fetching up to {sample_size} recent rows from event_market_analysis "
          f"({window_days}d window)...", file=sys.stderr)
    rows = await _fetch_recent_analyses(window_days, sample_size)
    print(f"  → {len(rows)} rows loaded; replaying v2 in parallel...", file=sys.stderr)

    # 5-way concurrency keeps us under the OpenAI rate limit while
    # finishing 50 calls in ~15-20s on gpt-4o-mini.
    sem = asyncio.Semaphore(5)

    async def _bounded(row: dict) -> dict:
        async with sem:
            return await _replay_one(row)

    results = await asyncio.gather(*(_bounded(r) for r in rows))

    _emit_markdown_report(results)
    if json_out:
        Path(json_out).write_text(json.dumps(results, default=str, indent=2))
        print(f"\nFull JSON dump → {json_out}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--window-days", type=int, default=14)
    p.add_argument("--sample-size", type=int, default=50,
                   help="Max number of rows to replay. Each row = 1 OpenAI call (~$0.001 on gpt-4o-mini).")
    p.add_argument("--json-out", default=None,
                   help="Optional path for the full per-row JSON dump.")
    args = p.parse_args()
    return asyncio.run(main_async(args.window_days, args.sample_size, args.json_out))


if __name__ == "__main__":
    sys.exit(main())
