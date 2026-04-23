import pytest

from app.measurement.metrics import (
    brier_from_outcome,
    simulated_pnl_eur,
    wilson_ci95,
)


# -- Wilson CI95 ------------------------------------------------------
def test_wilson_ci95_center_when_full_agreement():
    lo, hi = wilson_ci95(n=100, k=50)
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61


def test_wilson_ci95_k_zero():
    lo, hi = wilson_ci95(n=10, k=0)
    assert lo == pytest.approx(0.0, abs=1e-6)
    assert 0 < hi < 0.31


def test_wilson_ci95_k_equals_n():
    lo, hi = wilson_ci95(n=10, k=10)
    assert hi == pytest.approx(1.0, abs=1e-6)
    assert 0.69 < lo < 1.0


def test_wilson_ci95_n_zero_returns_zero_one():
    lo, hi = wilson_ci95(n=0, k=0)
    assert lo == 0.0 and hi == 1.0


def test_wilson_ci95_small_sample_matches_known_fixture():
    # n=24, k=11 -> computed Wilson CI95 ~ (0.279, 0.649)
    lo, hi = wilson_ci95(n=24, k=11)
    assert lo == pytest.approx(0.279, abs=0.005)
    assert hi == pytest.approx(0.649, abs=0.005)


# -- Brier ------------------------------------------------------------
def test_brier_yes_won_high_confidence():
    # said P(YES) = 0.85, YES won -> brier = (0.85 - 1)^2 = 0.0225
    assert brier_from_outcome(probability=0.85, resolved_binary=1) == pytest.approx(0.0225)


def test_brier_no_won_high_confidence():
    # said P(YES) = 0.1, NO won -> brier = (0.1 - 0)^2 = 0.01
    assert brier_from_outcome(probability=0.1, resolved_binary=0) == pytest.approx(0.01)


def test_brier_none_when_ambiguous():
    assert brier_from_outcome(probability=0.5, resolved_binary=None) is None


# -- P&L --------------------------------------------------------------
def test_pnl_buy_yes_winning():
    # stake 10, BUY_YES at 0.6, resolved at 1.0 -> 10 * (1.0 - 0.6) = 4
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=1.0
    ) == pytest.approx(4.0)


def test_pnl_buy_yes_losing():
    # stake 10, BUY_YES at 0.6, resolved at 0.0 -> 10 * (0 - 0.6) = -6
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=0.0
    ) == pytest.approx(-6.0)


def test_pnl_buy_no_winning():
    # BUY_NO at 0.3, resolved at 0 -> 10 * (0.3 - 0) = 3
    assert simulated_pnl_eur(
        direction="BUY_NO", probability=0.3, price_resolved=0.0
    ) == pytest.approx(3.0)


def test_pnl_partial_resolution_captured():
    # BUY_YES at 0.6, resolved at 0.7 -> 10 * (0.7 - 0.6) = 1
    assert simulated_pnl_eur(
        direction="BUY_YES", probability=0.6, price_resolved=0.7
    ) == pytest.approx(1.0)
