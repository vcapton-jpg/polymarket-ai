"""Pin the LEVIER-1 spread-gate decision logic.

The gate has two independent knobs:

  * `signal_max_spread_pp`  — reject when a KNOWN spread (bid & ask
    both present) exceeds the threshold.
  * `reject_unknown_spread` — reject markets with NO quoted book
    (bid or ask missing) entirely.

Both are inert unless `enable_max_spread_filter` is True. The pure
decision is extracted here so it can be unit-tested without the
DB-backed SignalBuilder.
"""

from __future__ import annotations

import pytest


def _spread_gate_decision(
    *,
    enabled: bool,
    best_bid: float | None,
    best_ask: float | None,
    max_spread_pp: float,
    reject_unknown: bool,
) -> str:
    """Mirror of the inline gate in SignalBuilder.build_signal.

    Returns one of: "pass", "reject_wide", "reject_unknown".
    Single source of truth — if the gate logic changes in
    signal_builder it must change here too.
    """
    if not enabled:
        return "pass"
    has_book = best_bid is not None and best_ask is not None
    if has_book:
        # round to 4 dp — guards against float noise at the boundary
        # (0.52-0.50 == 0.020000000000000018 in IEEE-754).
        spread = round(float(best_ask) - float(best_bid), 4)
        if spread > max_spread_pp:
            return "reject_wide"
        return "pass"
    if reject_unknown:
        return "reject_unknown"
    return "pass"


def test_disabled_gate_is_a_noop():
    # Even a pathologically wide spread passes when the master switch is off.
    assert _spread_gate_decision(
        enabled=False, best_bid=0.10, best_ask=0.90,
        max_spread_pp=0.02, reject_unknown=True,
    ) == "pass"


def test_tight_book_passes():
    # 1 pp spread on a 0.50 market — well under the 2 pp gate.
    assert _spread_gate_decision(
        enabled=True, best_bid=0.495, best_ask=0.505,
        max_spread_pp=0.02, reject_unknown=True,
    ) == "pass"


def test_wide_book_rejected():
    # 5 pp spread — over the 2 pp gate.
    assert _spread_gate_decision(
        enabled=True, best_bid=0.40, best_ask=0.45,
        max_spread_pp=0.02, reject_unknown=False,
    ) == "reject_wide"


def test_spread_exactly_at_threshold_passes():
    # Boundary: spread == threshold is NOT > threshold → pass.
    d = _spread_gate_decision(
        enabled=True, best_bid=0.50, best_ask=0.52,
        max_spread_pp=0.02, reject_unknown=False,
    )
    assert d == "pass"


def test_unknown_book_passes_when_reject_unknown_false():
    # No bid/ask, lenient mode → keep the signal (volume preserved).
    assert _spread_gate_decision(
        enabled=True, best_bid=None, best_ask=None,
        max_spread_pp=0.02, reject_unknown=False,
    ) == "pass"


def test_unknown_book_rejected_when_reject_unknown_true():
    # No bid/ask, strict mode → reject (the −0.67 % illiquid bucket).
    assert _spread_gate_decision(
        enabled=True, best_bid=None, best_ask=None,
        max_spread_pp=0.02, reject_unknown=True,
    ) == "reject_unknown"


@pytest.mark.parametrize("bid,ask", [(0.40, None), (None, 0.45)])
def test_half_book_treated_as_unknown(bid, ask):
    # Only one side quoted = not a usable spread = unknown.
    assert _spread_gate_decision(
        enabled=True, best_bid=bid, best_ask=ask,
        max_spread_pp=0.02, reject_unknown=True,
    ) == "reject_unknown"
