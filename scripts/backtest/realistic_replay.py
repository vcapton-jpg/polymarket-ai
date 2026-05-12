"""Realistic backtest — simulate trades end-to-end with spread + dynamic exit.

Why this exists
---------------
The existing `scripts/backtest/replay.py` computes "RTP" as the average
signed price move at a fixed horizon (t+1h). That's a clean **directional
proxy** — perfect for comparing v1 vs v2 prompts on the same dataset —
but it is NOT what a user actually pockets:

  * the price used is `last_trade_price` (mid-ish), but you'd actually
    pay the **ask** on entry and receive the **bid** on exit. On
    Polymarket the spread is typically 1-3 pp, which silently caps
    your edge at ~7.5 % relative move just to break even on a 0.40
    market.
  * the horizon is **fixed** at t+1h — you never actually hold a
    position for exactly 1 h. In practice you take profit when the
    price hits some target, you stop-loss when it goes against you,
    you hold to resolution if neither happens.
  * ties (move == 0) are silently dropped from the proxy, but they
    correspond to **realized losses** equal to the spread cost.

This script replays the same 30 d of prod signals through a more
honest model:

  * `entry_price = mid + spread/2`     for BUY_YES  (or `(1-mid) + spread/2` for BUY_NO)
  * `exit_price  = mid - spread/2`     symmetrically
  * walk t+5min → t+15min → t+1h → t+24h, exit at the first checkpoint
    where SL or TP is hit, else exit at t+24h ("max-hold")

Output is a markdown comparison of:
  * the theoretical RTP (current backtest replay shape)
  * the realized RTP at several (spread, SL, TP) settings
  * a split by `llm_model_version` so we can see whether v2 keeps its
    edge after the spread haircut

Usage
-----
Run from the API container so DB access "just works":

    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T app python -m scripts.backtest.realistic_replay \\
      --window-days 30 --spread-pp 0.03 --stop-loss-pct 10 --take-profit-pct 25'

Read-only — no DB writes.
"""

from __future__ import annotations

import argparse
import asyncio
import math
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

# Repo root on path so we can run as a CLI module from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ──────────────────────────────────────────────────────────────────────
# Trade simulation primitives — pure functions, easy to unit-test
# ──────────────────────────────────────────────────────────────────────


def _entry_price(direction: str, mid: float, spread_pp: float) -> float:
    """Price the user pays on entry, given `mid` is the YES mid.

    BUY_YES: cost = mid + spread/2 (you pay the YES ask)
    BUY_NO:  cost = (1 - mid) + spread/2 (you pay the NO ask)
    Anything else: 0 (rejected upstream — should never reach here).
    """
    d = (direction or "").upper()
    half = spread_pp / 2
    if d in ("BUY_YES", "YES", "UP"):
        return mid + half
    if d in ("BUY_NO", "NO", "DOWN"):
        return (1.0 - mid) + half
    return 0.0


def _exit_price(direction: str, mid: float, spread_pp: float) -> float:
    """Price the user receives on exit, given `mid` is the YES mid.

    BUY_YES: receive = mid - spread/2 (you sell at the YES bid)
    BUY_NO:  receive = (1 - mid) - spread/2 (you sell at the NO bid)
    """
    d = (direction or "").upper()
    half = spread_pp / 2
    if d in ("BUY_YES", "YES", "UP"):
        return max(0.0, mid - half)
    if d in ("BUY_NO", "NO", "DOWN"):
        return max(0.0, (1.0 - mid) - half)
    return 0.0


def _pnl_pct(direction: str, entry_mid: float, exit_mid: float, spread_pp: float) -> float:
    """Realized PnL % for a unit-stake trade between two mids."""
    entry = _entry_price(direction, entry_mid, spread_pp)
    if entry <= 0:
        return 0.0
    exit_p = _exit_price(direction, exit_mid, spread_pp)
    return (exit_p - entry) / entry * 100.0


def simulate_trade(
    direction: str,
    entry_mid: float,
    checkpoints: Sequence[tuple[str, float | None]],
    spread_pp: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> dict[str, Any]:
    """Walk checkpoints, exit at the first SL/TP trigger, else at the
    last available checkpoint.

    `checkpoints` is a list of (label, mid_or_None) in chronological
    order. None entries (missing snapshots) are skipped without
    aborting the simulation.

    Returns:
        {
          "exit_reason":  "take_profit" | "stop_loss" | "max_hold" | "no_checkpoint",
          "exit_label":   "t5min" | "t15min" | "t1h" | "t24h" | None,
          "exit_mid":     0.45 | None,
          "pnl_pct":      4.82,
          "checkpoints_seen": 3,
        }
    """
    last_seen_label: str | None = None
    last_seen_mid: float | None = None
    seen_count = 0

    for label, mid in checkpoints:
        if mid is None:
            continue
        seen_count += 1
        last_seen_label = label
        last_seen_mid = mid

        pnl = _pnl_pct(direction, entry_mid, mid, spread_pp)
        if pnl >= take_profit_pct:
            return {
                "exit_reason": "take_profit",
                "exit_label": label,
                "exit_mid": mid,
                "pnl_pct": pnl,
                "checkpoints_seen": seen_count,
            }
        if pnl <= -stop_loss_pct:
            return {
                "exit_reason": "stop_loss",
                "exit_label": label,
                "exit_mid": mid,
                "pnl_pct": pnl,
                "checkpoints_seen": seen_count,
            }

    if last_seen_label is None:
        return {
            "exit_reason": "no_checkpoint",
            "exit_label": None,
            "exit_mid": None,
            "pnl_pct": 0.0,
            "checkpoints_seen": 0,
        }

    return {
        "exit_reason": "max_hold",
        "exit_label": last_seen_label,
        "exit_mid": last_seen_mid,
        "pnl_pct": _pnl_pct(direction, entry_mid, last_seen_mid, spread_pp),
        "checkpoints_seen": seen_count,
    }


# ──────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────


async def _fetch_signals(window_days: int) -> list[dict]:
    """Load signals + outcome snapshots from the prod DB."""
    from sqlalchemy import text

    from app.db.database import get_session_factory

    sql = text(
        f"""
        SELECT
            sig.id,
            sig.direction,
            sig.market_price_at_signal,
            sig.llm_model_version,
            sig.created_at,
            so.price_t5min,
            so.price_t15min,
            so.price_t1h,
            so.price_t24h
        FROM signals sig
        JOIN signal_outcomes so ON so.signal_id = sig.id
        WHERE sig.created_at > NOW() - INTERVAL '{int(window_days)} days'
          AND sig.market_price_at_signal IS NOT NULL
          AND so.price_t1h IS NOT NULL  -- need at least one resolved snapshot
        """
    )

    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        rows = (await session.execute(sql)).mappings().all()

    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id": r["id"],
                "direction": r["direction"],
                "entry_mid": float(r["market_price_at_signal"]),
                "llm_model_version": r["llm_model_version"] or "unknown",
                "checkpoints": [
                    ("t5min",  float(r["price_t5min"])  if r["price_t5min"]  is not None else None),
                    ("t15min", float(r["price_t15min"]) if r["price_t15min"] is not None else None),
                    ("t1h",    float(r["price_t1h"])    if r["price_t1h"]    is not None else None),
                    ("t24h",   float(r["price_t24h"])   if r["price_t24h"]   is not None else None),
                ],
            }
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Aggregation + reporting
# ──────────────────────────────────────────────────────────────────────


def _wilson_ci_95(wins: int, n: int) -> tuple[float | None, float | None]:
    """Mirror the helper from app/api/routes/admin_stats.py — Wilson 95 %."""
    if n <= 0:
        return None, None
    z = 1.96
    p = wins / n
    denom = 1.0 + (z * z) / n
    center = (p + (z * z) / (2.0 * n)) / denom
    half = (z * math.sqrt(max(0.0, p * (1 - p) / n + (z * z) / (4.0 * n * n)))) / denom
    return round(100.0 * (center - half), 2), round(100.0 * (center + half), 2)


def aggregate(results: list[dict]) -> dict[str, Any]:
    """Crunch the per-signal outcomes into the summary the report renders."""
    n = len(results)
    if n == 0:
        return {"n": 0}

    pnls = [r["pnl_pct"] for r in results]
    wins_n = sum(1 for p in pnls if p > 0)
    losses_n = sum(1 for p in pnls if p < 0)
    ties_n = n - wins_n - losses_n  # exact zero PnL — rare with spread but possible

    rtp_mean = statistics.fmean(pnls) if pnls else 0.0
    rtp_sd = statistics.stdev(pnls) if len(pnls) >= 2 else 0.0
    rtp_se = rtp_sd / math.sqrt(n) if n >= 2 else 0.0
    t_stat = rtp_mean / rtp_se if rtp_se > 0 else None

    winrate = 100.0 * wins_n / (wins_n + losses_n) if (wins_n + losses_n) else None
    ci_low, ci_high = _wilson_ci_95(wins_n, wins_n + losses_n)

    exit_reason_counts = Counter(r["exit_reason"] for r in results)

    return {
        "n": n,
        "wins": wins_n,
        "losses": losses_n,
        "ties": ties_n,
        "winrate_pct": round(winrate, 2) if winrate is not None else None,
        "ci_low_95": ci_low,
        "ci_high_95": ci_high,
        "rtp_mean_pct": round(rtp_mean, 3),
        "rtp_sd_pct": round(rtp_sd, 3),
        "rtp_se_pct": round(rtp_se, 3),
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
        "significant_95": (abs(t_stat) >= 1.96) if t_stat is not None else False,
        "exit_reasons": dict(exit_reason_counts),
    }


def run_simulation(
    signals: list[dict],
    spread_pp: float,
    stop_loss_pct: float,
    take_profit_pct: float,
) -> list[dict]:
    """Apply `simulate_trade` to every signal and return the enriched list."""
    out: list[dict] = []
    for s in signals:
        sim = simulate_trade(
            direction=s["direction"],
            entry_mid=s["entry_mid"],
            checkpoints=s["checkpoints"],
            spread_pp=spread_pp,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
        )
        out.append({**s, **sim})
    return out


def _format_table(rows: list[dict], cols: list[tuple[str, str]]) -> str:
    """Tiny markdown-table helper. `cols` = list of (label, key)."""
    header = "| " + " | ".join(c[0] for c in cols) + " |"
    sep    = "|" + "|".join("---" for _ in cols) + "|"
    lines = [header, sep]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(c[1], "—")) for c in cols) + " |")
    return "\n".join(lines)


def _emit_report(
    *,
    window_days: int,
    n_input: int,
    spread_pp: float,
    sl: float,
    tp: float,
    overall: dict,
    by_model: dict[str, dict],
    sensitivity: list[dict],
) -> None:
    print(f"# Realistic backtest report — {window_days} d window, n={n_input}")
    print()
    print(f"**Trade-model parameters:** spread = {spread_pp*100:.1f} pp, "
          f"stop-loss = −{sl:.1f} %, take-profit = +{tp:.1f} %")
    print()

    # Overall
    print("## Overall (all signals, full 30 d, current trade-model)")
    print()
    print(_format_table([overall], [
        ("n", "n"),
        ("wins", "wins"),
        ("losses", "losses"),
        ("ties", "ties"),
        ("winrate %", "winrate_pct"),
        ("CI95 low %", "ci_low_95"),
        ("CI95 high %", "ci_high_95"),
        ("RTP %", "rtp_mean_pct"),
        ("SE %", "rtp_se_pct"),
        ("t-stat", "t_stat"),
        ("sig@95?", "significant_95"),
    ]))
    print()
    print("Exit reasons:", overall.get("exit_reasons"))
    print()

    # By model version
    print("## Per `llm_model_version`")
    print()
    rows = []
    for mv, agg in sorted(by_model.items(), key=lambda kv: -(kv[1].get("n") or 0)):
        rows.append({"model": f"`{mv}`", **agg})
    print(_format_table(rows, [
        ("model", "model"),
        ("n", "n"),
        ("winrate %", "winrate_pct"),
        ("CI95 low %", "ci_low_95"),
        ("CI95 high %", "ci_high_95"),
        ("RTP %", "rtp_mean_pct"),
        ("t-stat", "t_stat"),
        ("sig@95?", "significant_95"),
    ]))
    print()

    # Sensitivity sweep
    print("## Sensitivity to (spread, stop-loss, take-profit)")
    print()
    print(_format_table(sensitivity, [
        ("spread pp", "spread_pp"),
        ("SL %", "sl"),
        ("TP %", "tp"),
        ("n", "n"),
        ("winrate %", "winrate_pct"),
        ("CI95 low %", "ci_low_95"),
        ("RTP %", "rtp_mean_pct"),
        ("t-stat", "t_stat"),
        ("sig@95?", "significant_95"),
    ]))


# ──────────────────────────────────────────────────────────────────────
# Entrypoint
# ──────────────────────────────────────────────────────────────────────


async def main_async(args) -> int:
    print(f"Loading {args.window_days} d of signals...", file=sys.stderr)
    signals = await _fetch_signals(args.window_days)
    print(f"  → {len(signals)} signals with outcomes", file=sys.stderr)

    # Primary run with the headline (spread, SL, TP)
    sims = run_simulation(
        signals,
        spread_pp=args.spread_pp,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
    )
    overall = aggregate(sims)

    by_model: dict[str, dict] = {}
    for mv in sorted({s["llm_model_version"] for s in sims}):
        subset = [s for s in sims if s["llm_model_version"] == mv]
        by_model[mv] = aggregate(subset)

    # Sensitivity sweep — small grid to surface where the strategy works
    sweep_configs = [
        (0.00, args.stop_loss_pct, args.take_profit_pct),   # zero-spread reference
        (0.02, args.stop_loss_pct, args.take_profit_pct),
        (0.03, args.stop_loss_pct, args.take_profit_pct),   # headline
        (0.05, args.stop_loss_pct, args.take_profit_pct),
        (args.spread_pp, 5.0,  args.take_profit_pct),       # tighter SL
        (args.spread_pp, 20.0, args.take_profit_pct),       # looser SL
        (args.spread_pp, args.stop_loss_pct, 10.0),         # tighter TP
        (args.spread_pp, args.stop_loss_pct, 50.0),         # looser TP
        (args.spread_pp, 999.0, 999.0),                     # no SL/TP — exits at t+24h only
    ]
    sensitivity: list[dict] = []
    for spread, sl, tp in sweep_configs:
        sub = run_simulation(signals, spread_pp=spread, stop_loss_pct=sl, take_profit_pct=tp)
        agg = aggregate(sub)
        sensitivity.append({
            "spread_pp": round(spread * 100, 1),
            "sl": sl if sl < 100 else "∞",
            "tp": tp if tp < 100 else "∞",
            **agg,
        })

    _emit_report(
        window_days=args.window_days,
        n_input=len(signals),
        spread_pp=args.spread_pp,
        sl=args.stop_loss_pct,
        tp=args.take_profit_pct,
        overall=overall,
        by_model=by_model,
        sensitivity=sensitivity,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--window-days", type=int, default=30)
    p.add_argument("--spread-pp", type=float, default=0.03,
                   help="Bid-ask spread in price points (0.03 = 3 pp = typical Polymarket).")
    p.add_argument("--stop-loss-pct", type=float, default=10.0,
                   help="Exit if realized PnL <= -X %% at any checkpoint.")
    p.add_argument("--take-profit-pct", type=float, default=25.0,
                   help="Exit if realized PnL >= +X %% at any checkpoint.")
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
