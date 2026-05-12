"""Unit tests for the realistic backtest simulator (entry/exit + spread).

Pin the math so a future refactor can't silently flip a sign or drop
the spread term. Each test isolates one property — entry-side math,
exit-side math, end-to-end break-even, and the exit-decision logic
(SL hit, TP hit, max-hold fallback, all-checkpoints-missing).
"""

from __future__ import annotations

import pytest

from scripts.backtest.realistic_replay import (
    _entry_price,
    _exit_price,
    _pnl_pct,
    aggregate,
    simulate_trade,
)

# ──────────────────────────────────────────────────────────────────────
# Entry / exit price math
# ──────────────────────────────────────────────────────────────────────


def test_buy_yes_entry_pays_ask():
    # mid 0.40, spread 3 pp → user pays the ask = 0.40 + 0.015 = 0.415
    assert _entry_price("BUY_YES", 0.40, 0.03) == pytest.approx(0.415, rel=1e-9)


def test_buy_no_entry_pays_no_ask():
    # mid 0.40 → NO mid = 0.60, NO ask = 0.60 + 0.015 = 0.615
    assert _entry_price("BUY_NO", 0.40, 0.03) == pytest.approx(0.615, rel=1e-9)


def test_buy_yes_exit_receives_bid():
    # mid 0.45, spread 3 pp → user receives the bid = 0.45 - 0.015 = 0.435
    assert _exit_price("BUY_YES", 0.45, 0.03) == pytest.approx(0.435, rel=1e-9)


def test_buy_no_exit_receives_no_bid():
    # mid 0.45 → NO mid = 0.55, NO bid = 0.55 - 0.015 = 0.535
    assert _exit_price("BUY_NO", 0.45, 0.03) == pytest.approx(0.535, rel=1e-9)


def test_exit_price_never_negative_under_extreme_spread():
    # Pathological: very wide spread on a deep-NO mid → exit price floored at 0.
    assert _exit_price("BUY_YES", 0.01, 0.10) == 0.0


# ──────────────────────────────────────────────────────────────────────
# PnL math — the headline claim of the doc
# ──────────────────────────────────────────────────────────────────────


def test_pnl_buy_yes_with_favourable_move():
    # mid 0.40 → 0.45, spread 3 pp
    # entry 0.415, exit 0.435 → pnl = (0.435 - 0.415) / 0.415 = +4.82 %
    assert _pnl_pct("BUY_YES", 0.40, 0.45, 0.03) == pytest.approx(4.819, abs=0.01)


def test_pnl_break_even_requires_move_equal_to_spread():
    # On a 0.50 market with 3 pp spread, you need the mid to move
    # exactly +3 pp (to 0.53) to break even on BUY_YES.
    assert _pnl_pct("BUY_YES", 0.50, 0.53, 0.03) == pytest.approx(0.0, abs=1e-4)


def test_pnl_small_move_against_spread_is_loss():
    # A +1 pp move on a 0.50 mid with 3 pp spread → still a loss.
    assert _pnl_pct("BUY_YES", 0.50, 0.51, 0.03) < 0


def test_pnl_buy_no_with_favourable_move():
    # BUY_NO at mid 0.60 → 0.55 means YES dropped, NO went up.
    # NO entry: 0.40 + 0.015 = 0.415
    # NO exit:  0.45 - 0.015 = 0.435
    # pnl = +4.82 %
    assert _pnl_pct("BUY_NO", 0.60, 0.55, 0.03) == pytest.approx(4.819, abs=0.01)


def test_pnl_zero_when_direction_unknown():
    # Defensive — if direction is gibberish the entry price collapses
    # to 0 and we return 0 instead of NaN/divide-by-zero.
    assert _pnl_pct("???", 0.50, 0.55, 0.03) == 0.0


# ──────────────────────────────────────────────────────────────────────
# simulate_trade — exit-decision logic
# ──────────────────────────────────────────────────────────────────────


def test_simulate_take_profit_at_first_checkpoint_that_hits_tp():
    # BUY_YES from 0.40. Spread 0 to make the arithmetic obvious.
    # t5min @ 0.41 → pnl ~2.5 % (no TP)
    # t15min @ 0.55 → pnl ~37.5 % (TP at +25 %)
    # Should exit at t15min with take_profit, NOT walk further.
    out = simulate_trade(
        direction="BUY_YES",
        entry_mid=0.40,
        checkpoints=[("t5min", 0.41), ("t15min", 0.55), ("t1h", 0.99), ("t24h", 0.99)],
        spread_pp=0.0,
        stop_loss_pct=10.0,
        take_profit_pct=25.0,
    )
    assert out["exit_reason"] == "take_profit"
    assert out["exit_label"] == "t15min"
    assert out["pnl_pct"] == pytest.approx(37.5, abs=0.1)


def test_simulate_stop_loss_at_first_checkpoint_that_hits_sl():
    # BUY_YES from 0.40 with 10 % SL. Sequence:
    # t5min @ 0.39  → pnl ≈ -2.5 %  (no SL)
    # t15min @ 0.36 → pnl = -10.0 % (SL trigger — should exit here)
    # t1h @ 0.30, t24h @ 0.99 → must NOT be walked
    out = simulate_trade(
        direction="BUY_YES",
        entry_mid=0.40,
        checkpoints=[("t5min", 0.39), ("t15min", 0.36), ("t1h", 0.30), ("t24h", 0.99)],
        spread_pp=0.0,
        stop_loss_pct=10.0,
        take_profit_pct=25.0,
    )
    assert out["exit_reason"] == "stop_loss"
    assert out["exit_label"] == "t15min"
    assert out["pnl_pct"] == pytest.approx(-10.0, abs=0.001)
    assert out["checkpoints_seen"] == 2  # didn't walk past t15min


def test_simulate_max_hold_when_neither_threshold_is_hit():
    # Sideways market — never triggers SL or TP, exits at t+24h.
    out = simulate_trade(
        direction="BUY_YES",
        entry_mid=0.50,
        checkpoints=[("t5min", 0.51), ("t15min", 0.49), ("t1h", 0.52), ("t24h", 0.51)],
        spread_pp=0.0,
        stop_loss_pct=10.0,
        take_profit_pct=25.0,
    )
    assert out["exit_reason"] == "max_hold"
    assert out["exit_label"] == "t24h"


def test_simulate_skips_missing_snapshots_without_aborting():
    # Real prod data has gaps (worker restart, capture race, etc.).
    # Missing checkpoints must be skipped, not crash the sim.
    out = simulate_trade(
        direction="BUY_YES",
        entry_mid=0.40,
        checkpoints=[("t5min", None), ("t15min", None), ("t1h", 0.55), ("t24h", None)],
        spread_pp=0.0,
        stop_loss_pct=10.0,
        take_profit_pct=25.0,
    )
    # t1h @ 0.55 → pnl = +37.5 % → take-profit
    assert out["exit_reason"] == "take_profit"
    assert out["exit_label"] == "t1h"
    assert out["checkpoints_seen"] == 1


def test_simulate_returns_no_checkpoint_when_everything_is_missing():
    # Defensive — all four snapshots are NULL. Treat as a non-trade,
    # PnL 0, distinct exit_reason so the aggregator can spot it.
    out = simulate_trade(
        direction="BUY_YES",
        entry_mid=0.40,
        checkpoints=[("t5min", None), ("t15min", None), ("t1h", None), ("t24h", None)],
        spread_pp=0.03,
        stop_loss_pct=10.0,
        take_profit_pct=25.0,
    )
    assert out["exit_reason"] == "no_checkpoint"
    assert out["pnl_pct"] == 0.0
    assert out["checkpoints_seen"] == 0


# ──────────────────────────────────────────────────────────────────────
# aggregate — sanity on the summary stats
# ──────────────────────────────────────────────────────────────────────


def test_aggregate_simple_three_signals():
    """Three synthetic trades: +10 %, -5 %, 0 %. Sanity-check the
    counts, winrate, and that ties don't pollute the win/loss count."""
    results = [
        {"pnl_pct": 10.0, "exit_reason": "take_profit", "llm_model_version": "x"},
        {"pnl_pct": -5.0, "exit_reason": "stop_loss",   "llm_model_version": "x"},
        {"pnl_pct":  0.0, "exit_reason": "max_hold",    "llm_model_version": "x"},
    ]
    agg = aggregate(results)
    assert agg["n"] == 3
    assert agg["wins"] == 1
    assert agg["losses"] == 1
    assert agg["ties"] == 1
    # winrate denominator = wins + losses = 2 → 1/2 = 50 %
    assert agg["winrate_pct"] == 50.0
    # mean of [10, -5, 0] = 1.667
    assert agg["rtp_mean_pct"] == pytest.approx(1.667, abs=0.01)
    assert agg["exit_reasons"]["take_profit"] == 1
    assert agg["exit_reasons"]["stop_loss"] == 1
    assert agg["exit_reasons"]["max_hold"] == 1


def test_aggregate_empty_input():
    """Empty list must not crash — useful for the per-model-version
    breakdown where some versions may have 0 signals in window."""
    agg = aggregate([])
    assert agg == {"n": 0}
