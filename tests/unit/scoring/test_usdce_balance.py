"""Pin the USDC.e base-unit → float conversion (P1 deposit confirmation).

USDC.e on Polygon has 6 decimals. The DepositModal shows this number
to the user as "X USDC.e received" — an off-by-10^n here would tell
someone they received 1 000 000 USDC when they tipped 1, so it's
worth a hard test even though it's one division.
"""

from __future__ import annotations

from app.trading.safe_deployer import _usdce_units_to_float


def test_one_usdc():
    # 1 USDC.e = 1_000_000 base units (6 decimals)
    assert _usdce_units_to_float(1_000_000) == 1.0


def test_zero():
    assert _usdce_units_to_float(0) == 0.0


def test_sub_unit_precision():
    # 2.50 USDC.e
    assert _usdce_units_to_float(2_500_000) == 2.5
    # smallest unit = 0.000001
    assert _usdce_units_to_float(1) == 1e-6


def test_large_balance():
    # 12 345.678901 USDC.e
    assert _usdce_units_to_float(12_345_678_901) == 12_345.678901


def test_typical_tip_amount():
    # A $5 Polymarket tip
    assert _usdce_units_to_float(5_000_000) == 5.0
