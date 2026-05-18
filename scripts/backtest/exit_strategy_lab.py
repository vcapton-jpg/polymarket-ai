"""Exit-strategy lab — LEVIER-3. Read-only.

The 3-day data (2026-05-18) showed a "wins often, small / loses
rarely, big" profile: winrate ~59 % but RTP negative. That's the
signature of holding positions to a FIXED horizon (t+1h) instead of
taking profit at the peak / cutting losses early. This script
quantifies how much PnL that leaves on the table by replaying every
signal under a battery of exit strategies and comparing realised RTP.

It does NOT change anything in prod. It produces the evidence needed
to decide whether the exit-execution work (LEVIER-4) is worth it:
if a *reachable* strategy (TP/SL/trailing) clearly beats the
fixed-horizon baseline, LEVIER-4 is justified; if it doesn't, we
don't waste two weeks building executable exits.

Strategies compared
-------------------
  fixed_t1h     baseline — what the proxy RTP measures today
  fixed_t24h    hold to the 24 h snapshot
  take_profit   exit at first checkpoint where pnl >= TP, else last
  stop_loss     exit at first checkpoint where pnl <= -SL, else last
  tp_sl         first of TP/SL to trigger, else last (= realistic_replay)
  trailing      exit when pnl falls `TRAIL` pts below the running peak
  oracle_best   exit at the best checkpoint  (UPPER bound, NOT reachable
                — shows the maximum PnL a perfect exit could capture)
  oracle_worst  exit at the worst checkpoint (LOWER bound — shows the
                downside a pathological exit would realise)

The gap between `oracle_best` and `fixed_t1h` is the size of the
prize. The gap between the best *reachable* strategy and `fixed_t1h`
is what LEVIER-4 can actually bank.

USAGE
-----
    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T app python -m scripts.backtest.exit_strategy_lab \\
      --window-days 7 --spread-pp 0.03'

Read-only — only SELECTs.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Callable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Reuse the audited primitives — single source of truth for the
# entry/exit/spread arithmetic.
from scripts.backtest.realistic_replay import (  # noqa: E402
    _fetch_signals,
    _pnl_pct,
    _wilson_ci_95,
)

# ──────────────────────────────────────────────────────────────────────
# Exit strategies — pure. Each takes the entry mid, the chronological
# (label, mid) checkpoints (None entries skipped), direction, spread,
# and returns (exit_label, pnl_pct).
# ──────────────────────────────────────────────────────────────────────

Checkpoint = tuple[str, float | None]


def _live(checkpoints: list[Checkpoint]) -> list[tuple[str, float]]:
    """Drop missing snapshots, keep chronological order."""
    return [(lbl, mid) for lbl, mid in checkpoints if mid is not None]


def _pnl(direction: str, entry_mid: float, exit_mid: float, spread_pp: float) -> float:
    """`_pnl_pct` rounded to 6 dp. Without this a pnl that is exactly
    on a threshold (e.g. (0.50-0.40)/0.40*100) comes out of IEEE-754
    as 24.999999999999996 and a `>= 25.0` take-profit never fires.
    Same float-noise class as the LEVIER-1 spread-gate fix."""
    return round(_pnl_pct(direction, entry_mid, exit_mid, spread_pp), 6)


def exit_fixed(
    label_target: str,
) -> Callable[[str, float, list[Checkpoint], float], tuple[str, float]]:
    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        if not live:
            return ("none", 0.0)
        # Prefer the requested horizon; fall back to the last available.
        chosen = next((c for c in live if c[0] == label_target), live[-1])
        return (chosen[0], _pnl(direction, entry_mid, chosen[1], spread_pp))

    return _strat


def exit_take_profit(tp_pct: float):
    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        for lbl, mid in live:
            pnl = _pnl(direction, entry_mid, mid, spread_pp)
            if pnl >= tp_pct:
                return (lbl, pnl)
        if not live:
            return ("none", 0.0)
        lbl, mid = live[-1]
        return (lbl, _pnl(direction, entry_mid, mid, spread_pp))

    return _strat


def exit_stop_loss(sl_pct: float):
    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        for lbl, mid in live:
            pnl = _pnl(direction, entry_mid, mid, spread_pp)
            if pnl <= -sl_pct:
                return (lbl, pnl)
        if not live:
            return ("none", 0.0)
        lbl, mid = live[-1]
        return (lbl, _pnl(direction, entry_mid, mid, spread_pp))

    return _strat


def exit_tp_sl(tp_pct: float, sl_pct: float):
    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        for lbl, mid in live:
            pnl = _pnl(direction, entry_mid, mid, spread_pp)
            if pnl >= tp_pct or pnl <= -sl_pct:
                return (lbl, pnl)
        if not live:
            return ("none", 0.0)
        lbl, mid = live[-1]
        return (lbl, _pnl(direction, entry_mid, mid, spread_pp))

    return _strat


def exit_trailing(trail_pct: float):
    """Exit when pnl drops `trail_pct` points below the running peak."""

    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        if not live:
            return ("none", 0.0)
        peak = float("-inf")
        for lbl, mid in live:
            pnl = _pnl(direction, entry_mid, mid, spread_pp)
            peak = max(peak, pnl)
            if peak - pnl >= trail_pct and peak > 0:
                # Only trail once we've been in profit — a trailing
                # stop on a position that never went green is just a
                # stop-loss, handled by the SL strategy.
                return (lbl, pnl)
        lbl, mid = live[-1]
        return (lbl, _pnl(direction, entry_mid, mid, spread_pp))

    return _strat


def exit_oracle(best: bool):
    """Non-reachable bound: exit at the best (or worst) checkpoint."""

    def _strat(direction, entry_mid, checkpoints, spread_pp):
        live = _live(checkpoints)
        if not live:
            return ("none", 0.0)
        scored = [
            (lbl, _pnl(direction, entry_mid, mid, spread_pp))
            for lbl, mid in live
        ]
        chosen = (max if best else min)(scored, key=lambda t: t[1])
        return chosen

    return _strat


STRATEGIES: dict[str, Callable] = {
    "fixed_t1h": exit_fixed("t1h"),
    "fixed_t24h": exit_fixed("t24h"),
    "take_profit_15": exit_take_profit(15.0),
    "take_profit_25": exit_take_profit(25.0),
    "stop_loss_10": exit_stop_loss(10.0),
    "tp25_sl10": exit_tp_sl(25.0, 10.0),
    "tp15_sl8": exit_tp_sl(15.0, 8.0),
    "trailing_10": exit_trailing(10.0),
    "trailing_15": exit_trailing(15.0),
    "oracle_best": exit_oracle(best=True),
    "oracle_worst": exit_oracle(best=False),
}


# ──────────────────────────────────────────────────────────────────────
# Aggregation
# ──────────────────────────────────────────────────────────────────────


def _agg(pnls: list[float]) -> dict:
    n = len(pnls)
    if n == 0:
        return {"n": 0}
    wins = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p < 0)
    mean = sum(pnls) / n
    if n >= 2:
        var = sum((p - mean) ** 2 for p in pnls) / (n - 1)
        sd = var**0.5
        se = sd / (n**0.5)
        t = mean / se if se > 0 else None
    else:
        se = t = None
    wr = (100.0 * wins / (wins + losses)) if (wins + losses) else None
    ci_lo, ci_hi = _wilson_ci_95(wins, wins + losses)
    return {
        "n": n,
        "winrate": round(wr, 1) if wr is not None else None,
        "ci_lo": ci_lo,
        "ci_hi": ci_hi,
        "rtp": round(mean, 3),
        "t": round(t, 2) if t is not None else None,
        "sig": (abs(t) >= 1.96) if t is not None else False,
    }


def run(signals: list[dict], spread_pp: float) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name, strat in STRATEGIES.items():
        pnls = [
            strat(s["direction"], s["entry_mid"], s["checkpoints"], spread_pp)[1]
            for s in signals
        ]
        out[name] = _agg(pnls)
    return out


def _table(results: dict[str, dict], baseline_rtp: float) -> str:
    cols = ["strategy", "n", "winrate", "CI95", "RTP %", "Δ vs t1h", "t", "sig"]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    # Keep dict insertion order (baseline first, oracles last).
    for name, a in results.items():
        if a.get("n", 0) == 0:
            continue
        ci = (
            f"[{a['ci_lo']}, {a['ci_hi']}]"
            if a.get("ci_lo") is not None
            else "—"
        )
        delta = round(a["rtp"] - baseline_rtp, 3)
        lines.append(
            f"| {name} | {a['n']} | {a['winrate']} | {ci} | "
            f"{a['rtp']} | {delta:+.3f} | {a['t']} | {a['sig']} |"
        )
    return "\n".join(lines)


async def main_async(args) -> int:
    print(f"Loading {args.window_days} d of signals…", file=sys.stderr)
    signals = await _fetch_signals(args.window_days)
    # Keep only signals that have at least one outcome snapshot.
    signals = [
        s for s in signals
        if any(m is not None for _, m in s["checkpoints"])
    ]
    print(f"  → {len(signals)} signals with ≥1 snapshot", file=sys.stderr)

    # All signals
    res_all = run(signals, args.spread_pp)
    base_all = res_all["fixed_t1h"]["rtp"] if res_all["fixed_t1h"].get("n") else 0.0

    # v2 only — the regime we actually run in prod now
    v2 = [s for s in signals if (s.get("llm_model_version") or "").endswith("@v2")]
    res_v2 = run(v2, args.spread_pp)
    base_v2 = (
        res_v2["fixed_t1h"]["rtp"]
        if res_v2.get("fixed_t1h", {}).get("n")
        else 0.0
    )

    print(f"# Exit-strategy lab — {args.window_days} d, spread {args.spread_pp*100:.1f} pp")
    print()
    print(f"## All signals (n={len(signals)})")
    print()
    print(_table(res_all, base_all))
    print()
    print(f"## v2 only (n={len(v2)})")
    print()
    print(_table(res_v2, base_v2))
    print()
    print("---")
    print(
        "**Reading:** `oracle_best Δ vs t1h` = the maximum PnL a perfect "
        "exit could add. The best *reachable* strategy's Δ = what "
        "LEVIER-4 can actually bank. If that Δ is small or negative, "
        "skip the exit-execution work."
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--window-days", type=int, default=7)
    p.add_argument("--spread-pp", type=float, default=0.03)
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
