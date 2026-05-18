"""Pin the LEVIER-3 exit-strategy decision logic.

Each strategy is a pure function over the price checkpoint sequence.
Tests use spread_pp=0 so the PnL arithmetic is transparent
(_pnl_pct with 0 spread = simple relative move on the YES token).

Scenario for most tests: BUY_YES from mid 0.40. At 0 spread,
pnl% = (exit_mid - 0.40) / 0.40 * 100.
  0.44 → +10 %
  0.50 → +25 %
  0.36 → −10 %
  0.30 → −25 %
"""

from __future__ import annotations

import pytest

from scripts.backtest.exit_strategy_lab import (
    _agg,
    exit_fixed,
    exit_oracle,
    exit_stop_loss,
    exit_take_profit,
    exit_tp_sl,
    exit_trailing,
)

CK = [("t5min", 0.41), ("t15min", 0.50), ("t1h", 0.42), ("t24h", 0.30)]
#       +2.5 %          +25 %            +5 %            −25 %


def test_fixed_t1h_takes_the_t1h_snapshot():
    lbl, pnl = exit_fixed("t1h")("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t1h"
    assert pnl == pytest.approx(5.0)


def test_fixed_falls_back_to_last_when_target_missing():
    ck = [("t5min", 0.41), ("t15min", 0.50)]  # no t1h
    lbl, pnl = exit_fixed("t1h")("BUY_YES", 0.40, ck, 0.0)
    assert lbl == "t15min"  # last available
    assert pnl == pytest.approx(25.0)


def test_take_profit_exits_at_first_hit():
    # TP 25 → t15min @ 0.50 is the first to reach +25 %.
    lbl, pnl = exit_take_profit(25.0)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t15min"
    assert pnl == pytest.approx(25.0)


def test_take_profit_falls_through_to_last_when_never_hit():
    lbl, pnl = exit_take_profit(99.0)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t24h"
    assert pnl == pytest.approx(-25.0)


def test_stop_loss_exits_at_first_breach():
    # SL 10 → only t24h @ 0.30 (−25 %) breaches; earlier are positive.
    lbl, pnl = exit_stop_loss(10.0)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t24h"
    assert pnl == pytest.approx(-25.0)


def test_tp_sl_takes_whichever_triggers_first_chronologically():
    # t15min hits TP 25 before t24h hits SL 10 → exit t15min +25 %.
    lbl, pnl = exit_tp_sl(25.0, 10.0)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t15min"
    assert pnl == pytest.approx(25.0)


def test_trailing_exits_after_peak_drawdown():
    # Peak +25 % at t15min. t1h drops to +5 % → drawdown 20 pts ≥ 10
    # trail and peak was green → exit at t1h with +5 %.
    lbl, pnl = exit_trailing(10.0)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t1h"
    assert pnl == pytest.approx(5.0)


def test_trailing_does_not_trigger_if_never_green():
    # All red sequence — trailing must not fire (that's the SL's job),
    # falls through to last.
    ck = [("t5min", 0.39), ("t1h", 0.36), ("t24h", 0.34)]
    lbl, pnl = exit_trailing(5.0)("BUY_YES", 0.40, ck, 0.0)
    assert lbl == "t24h"
    assert pnl < 0


def test_oracle_best_picks_global_max():
    lbl, pnl = exit_oracle(best=True)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t15min"
    assert pnl == pytest.approx(25.0)


def test_oracle_worst_picks_global_min():
    lbl, pnl = exit_oracle(best=False)("BUY_YES", 0.40, CK, 0.0)
    assert lbl == "t24h"
    assert pnl == pytest.approx(-25.0)


def test_strategies_handle_all_missing_snapshots():
    empty = [("t5min", None), ("t1h", None)]
    for strat in (
        exit_fixed("t1h"),
        exit_take_profit(25.0),
        exit_stop_loss(10.0),
        exit_tp_sl(25.0, 10.0),
        exit_trailing(10.0),
        exit_oracle(best=True),
    ):
        lbl, pnl = strat("BUY_YES", 0.40, empty, 0.0)
        assert lbl == "none"
        assert pnl == 0.0


def test_buy_no_direction_pnl_sign_flips():
    # BUY_NO from 0.60: YES falling to 0.50 is +profit for NO.
    ck = [("t1h", 0.50)]
    _, pnl = exit_fixed("t1h")("BUY_NO", 0.60, ck, 0.0)
    assert pnl > 0


def test_agg_empty():
    assert _agg([]) == {"n": 0}


def test_agg_basic_stats():
    a = _agg([10.0, -5.0, 0.0, 20.0])
    assert a["n"] == 4
    # wins=2 (10,20), losses=1 (-5); winrate = 2/3 = 66.7 %
    assert a["winrate"] == 66.7
    assert a["rtp"] == 6.25  # mean of [10,-5,0,20]
