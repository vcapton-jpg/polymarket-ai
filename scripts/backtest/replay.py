"""Standalone backtest harness — apply a rule on historical signals.

Loads the joined `signals × signal_outcomes` table from the prod DB,
applies a `keep(signal: dict) -> bool` rule, and reports retention,
winrate (with Wilson CI95), RTP and t-stat. The harness is **read-only** —
it never writes back to the DB.

USAGE
-----
Run from the host shell (Tailscale SSH gives us the DB connection):

    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T worker-ingestion python -m scripts.backtest.replay \\
      --rule baseline --window-days 30'

Or locally if your `.env` points at the prod Postgres:

    python -m scripts.backtest.replay --rule dirprice_filter --window-days 30

Add a new rule under `scripts/backtest/rules/<name>.py` exporting
`def keep(signal: dict) -> bool`. The `signal` dict has the following
keys:

    id, direction, market_price_at_signal, signal_score, cosine_score,
    created_at, category, source_name, move_t1h_pct, move_t24h_pct

OUTPUT
------
Markdown summary on stdout + final JSON line (machine-parseable) for
piping into a comparison script.

T-005 in docs/PLAN_30D_SIGNAL_QUALITY.md.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Callable, Optional

# Add repo root to sys.path so `from app.db.database import ...` works.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def wilson_ci_95(wins: int, n: int) -> tuple[Optional[float], Optional[float]]:
    """Wilson score 95% interval (lower, upper) in percentage points."""
    if n <= 0:
        return None, None
    z = 1.96
    p = wins / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt(max(0.0, p * (1 - p) / n + (z * z) / (4.0 * n * n)))) / denom
    return round(100.0 * (center - half), 2), round(100.0 * (center + half), 2)


def signed_pnl_pct(direction: str, move_pct: float) -> float:
    """PnL/share for a unit-stake trade given the YES-price move %."""
    d = (direction or "").upper()
    if d in ("BUY_YES", "YES", "UP"):
        return float(move_pct)
    if d in ("BUY_NO", "NO", "DOWN"):
        return -float(move_pct)
    return 0.0


def is_win(direction: str, move_pct: float) -> Optional[bool]:
    """Tri-state: True (win) / False (loss) / None (tie, move == 0)."""
    if move_pct == 0:
        return None
    return signed_pnl_pct(direction, move_pct) > 0


async def fetch_signals(window_days: int) -> list[dict]:
    """Load joined signals × outcomes from the prod DB.

    Filters: created_at within window, move_t1h_pct not null,
    market_price_at_signal not null. (Same restrictions used by the
    /admin/stats/extended endpoint.)
    """
    from sqlalchemy import text

    from app.db.database import get_session_factory

    sql = text(
        f"""
        SELECT
            sig.id,
            sig.direction,
            sig.market_price_at_signal,
            sig.signal_score,
            sig.cosine_score,
            sig.created_at,
            COALESCE(m.category, 'unknown') AS category,
            so.move_t1h_pct,
            so.move_t24h_pct,
            (
                SELECT n.source_name
                FROM signal_articles sa
                JOIN news_clean nc ON nc.id = sa.news_clean_id
                JOIN news n ON n.id = nc.news_id
                WHERE sa.signal_id = sig.id
                ORDER BY sa.rank ASC
                LIMIT 1
            ) AS source_name
        FROM signals sig
        JOIN signal_outcomes so ON so.signal_id = sig.id
        LEFT JOIN markets m ON m.market_id = sig.market_id
        WHERE sig.created_at > NOW() - INTERVAL '{int(window_days)} days'
          AND so.move_t1h_pct IS NOT NULL
          AND sig.market_price_at_signal IS NOT NULL
    """
    )

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        rows = (await session.execute(sql)).mappings().all()
    return [
        {
            "id": r["id"],
            "direction": r["direction"],
            "market_price_at_signal": float(r["market_price_at_signal"])
            if r["market_price_at_signal"] is not None
            else None,
            "signal_score": float(r["signal_score"]) if r["signal_score"] is not None else None,
            "cosine_score": float(r["cosine_score"]) if r["cosine_score"] is not None else None,
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "category": r["category"],
            "source_name": r["source_name"],
            "move_t1h_pct": float(r["move_t1h_pct"]) if r["move_t1h_pct"] is not None else None,
            "move_t24h_pct": float(r["move_t24h_pct"]) if r["move_t24h_pct"] is not None else None,
        }
        for r in rows
    ]


def evaluate(rule_fn: Callable[[dict], bool], signals: list[dict]) -> dict:
    """Apply `rule_fn` over `signals` and compute aggregate metrics."""
    kept: list[dict] = []
    for s in signals:
        try:
            if rule_fn(s):
                kept.append(s)
        except Exception as e:
            print(f"  ! rule_fn raised on signal id={s.get('id')}: {type(e).__name__}: {e}", file=sys.stderr)

    n_total = len(signals)
    n_kept = len(kept)

    wins = sum(1 for s in kept if is_win(s["direction"], s["move_t1h_pct"]) is True)
    losses = sum(1 for s in kept if is_win(s["direction"], s["move_t1h_pct"]) is False)
    ties = sum(1 for s in kept if is_win(s["direction"], s["move_t1h_pct"]) is None)
    resolved = wins + losses

    winrate = (100.0 * wins / resolved) if resolved else None
    ci_low, ci_high = wilson_ci_95(wins, resolved)

    rtps_t1h = [signed_pnl_pct(s["direction"], s["move_t1h_pct"]) for s in kept]
    rtp_mean = sum(rtps_t1h) / len(rtps_t1h) if rtps_t1h else None
    if len(rtps_t1h) >= 2 and rtp_mean is not None:
        rtp_var = sum((r - rtp_mean) ** 2 for r in rtps_t1h) / (len(rtps_t1h) - 1)
        rtp_sd = math.sqrt(rtp_var)
        rtp_se = rtp_sd / math.sqrt(len(rtps_t1h))
        t_stat = rtp_mean / rtp_se if rtp_se > 0 else None
    else:
        rtp_sd = rtp_se = t_stat = None

    return {
        "n_input": n_total,
        "n_kept": n_kept,
        "retention_pct": round(100.0 * n_kept / n_total, 2) if n_total else None,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "winrate_pct": round(winrate, 2) if winrate is not None else None,
        "ci_low_95_pct": ci_low,
        "ci_high_95_pct": ci_high,
        "rtp_t1h_mean_pct": round(rtp_mean, 3) if rtp_mean is not None else None,
        "rtp_t1h_se_pct": round(rtp_se, 3) if rtp_se is not None else None,
        "rtp_t1h_t_stat": round(t_stat, 2) if t_stat is not None else None,
        "rtp_t1h_significant_at_95pct": (abs(t_stat) >= 1.96) if t_stat is not None else False,
    }


def print_markdown_report(rule_name: str, window_days: int, baseline: dict, candidate: Optional[dict] = None) -> None:
    """Pretty-print to stdout. If `candidate` given, also print baseline-vs-candidate delta table."""
    print()
    print(f"# Backtest report — rule=`{rule_name}` window={window_days}d")
    print()
    if candidate is None:
        rows = [("metric", "value"), *((k, v) for k, v in baseline.items())]
        widths = [max(len(str(r[i])) for r in rows) for i in range(2)]
        for r in rows:
            print(f"| {str(r[0]):{widths[0]}} | {str(r[1]):{widths[1]}} |")
        return
    keys = list(baseline.keys())
    print(f"| metric | baseline | {rule_name} |")
    print("|---|---:|---:|")
    for k in keys:
        print(f"| {k} | {baseline[k]} | {candidate[k]} |")


async def main_async(rule_name: str, window_days: int, compare_baseline: bool) -> int:
    try:
        mod = importlib.import_module(f"scripts.backtest.rules.{rule_name}")
    except ModuleNotFoundError:
        print(f"ERROR: rule '{rule_name}' not found under scripts/backtest/rules/", file=sys.stderr)
        return 2
    rule_fn = getattr(mod, "keep", None)
    if not callable(rule_fn):
        print(f"ERROR: rules.{rule_name} must export `def keep(signal: dict) -> bool`", file=sys.stderr)
        return 2

    print(f"Loading {window_days}d of signals from prod DB...", file=sys.stderr)
    signals = await fetch_signals(window_days)
    print(f"  → {len(signals)} signals with outcomes loaded.", file=sys.stderr)

    candidate = evaluate(rule_fn, signals)

    baseline = None
    if compare_baseline and rule_name != "baseline":
        from scripts.backtest.rules import baseline as baseline_mod

        baseline = evaluate(baseline_mod.keep, signals)

    print_markdown_report(rule_name, window_days, baseline or candidate, candidate if baseline else None)
    print()
    print("---")
    print(json.dumps({"rule": rule_name, "window_days": window_days, "candidate": candidate, "baseline": baseline}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--rule", required=True, help="Module name under scripts/backtest/rules/ (e.g. 'baseline', 'dirprice_filter')")
    p.add_argument("--window-days", type=int, default=30, help="Lookback window in days (default 30)")
    p.add_argument("--no-compare", action="store_true", help="Skip baseline-comparison output (only the candidate)")
    args = p.parse_args()
    return asyncio.run(main_async(args.rule, args.window_days, not args.no_compare))


if __name__ == "__main__":
    sys.exit(main())
