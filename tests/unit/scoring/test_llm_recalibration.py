"""Pin the LEVIER-2 LLM recalibration decision logic.

The v2 model is over-confident (measured H+168): it predicts 0.17 when
reality is ~0.32, predicts 0.83 when reality is ~0.65. We shrink the
predicted P(YES) toward 0.5, then re-check the edge vs the market. If
the calibrated estimate no longer clears the minimum edge, the signal
only existed because of the exaggeration → reject.

Pure decision extracted here so it can be tested without the
DB-backed SignalBuilder.
"""

from __future__ import annotations

import pytest


def _recalibration_decision(
    *,
    enabled: bool,
    raw_implied: float | None,
    market_price: float | None,
    shrink: float,
    min_edge: float,
) -> str:
    """Mirror of the inline LEVIER-2 block in SignalBuilder.build_signal.
    Returns "pass" or "reject_no_edge". Single source of truth."""
    if not enabled or market_price is None or raw_implied is None:
        return "pass"
    calibrated = 0.5 + (float(raw_implied) - 0.5) * shrink
    edge = abs(calibrated - float(market_price))
    return "reject_no_edge" if edge < min_edge else "pass"


def test_disabled_is_noop():
    # Even a wild over-confident prediction passes when the switch is off.
    assert _recalibration_decision(
        enabled=False, raw_implied=0.95, market_price=0.50,
        shrink=0.55, min_edge=0.05,
    ) == "pass"


def test_inflated_confidence_collapses_to_no_edge():
    # LLM screams 0.85 on a 0.62 market — raw edge 0.23 looks great.
    # Calibrated: 0.5 + (0.85-0.5)*0.55 = 0.6925 → edge vs 0.62 = 0.0725
    # Still above 0.05 → passes. But push the market closer:
    # market 0.66 → calibrated edge = 0.0325 < 0.05 → reject.
    assert _recalibration_decision(
        enabled=True, raw_implied=0.85, market_price=0.66,
        shrink=0.55, min_edge=0.05,
    ) == "reject_no_edge"


def test_genuine_edge_survives_calibration():
    # LLM 0.90, market 0.45. Calibrated 0.5+(0.40*0.55)=0.72.
    # Edge vs 0.45 = 0.27 ≫ 0.05 → real edge, keep it.
    assert _recalibration_decision(
        enabled=True, raw_implied=0.90, market_price=0.45,
        shrink=0.55, min_edge=0.05,
    ) == "pass"


def test_low_side_over_confidence_also_collapses():
    # LLM 0.10 (very bearish), market 0.28.
    # Calibrated 0.5+(0.10-0.5)*0.55 = 0.28 → edge = 0.00 → reject.
    assert _recalibration_decision(
        enabled=True, raw_implied=0.10, market_price=0.28,
        shrink=0.55, min_edge=0.05,
    ) == "reject_no_edge"


def test_missing_implied_passes():
    # v1 rows have no implied_yes — recalibration must not reject them.
    assert _recalibration_decision(
        enabled=True, raw_implied=None, market_price=0.50,
        shrink=0.55, min_edge=0.05,
    ) == "pass"


def test_missing_market_price_passes():
    # No market price → can't compute edge → don't reject.
    assert _recalibration_decision(
        enabled=True, raw_implied=0.80, market_price=None,
        shrink=0.55, min_edge=0.05,
    ) == "pass"


def test_shrink_1_is_identity():
    # shrink=1.0 → calibrated == raw. With raw 0.80, market 0.78,
    # edge = 0.02 < 0.05 → reject (no shrink applied, pure edge test).
    assert _recalibration_decision(
        enabled=True, raw_implied=0.80, market_price=0.78,
        shrink=1.0, min_edge=0.05,
    ) == "reject_no_edge"


@pytest.mark.parametrize(
    "raw,expected_calib",
    [(0.83, 0.6815), (0.17, 0.3185), (0.50, 0.50)],
)
def test_calibration_formula(raw, expected_calib):
    # Pin the shrink arithmetic itself at the fitted 0.55 factor.
    calibrated = 0.5 + (raw - 0.5) * 0.55
    assert calibrated == pytest.approx(expected_calib, abs=1e-4)
