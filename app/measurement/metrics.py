"""Pure math helpers used by the resolution hook + admin aggregation endpoint.

No SQL here — these operate on already-fetched numbers. Keeps the statistics
testable in isolation and identical whether called from the API, the CLI, or
the Celery worker.
"""

from __future__ import annotations

import math

# Z-score for 95% two-sided confidence (1.959963984540054)
_Z95 = 1.959963984540054


def wilson_ci95(n: int, k: int) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n at 95% confidence.

    Stable for small n (unlike the normal approximation). Edge cases:
    - n = 0 -> (0.0, 1.0) (no information)
    - k = 0 -> lower bound is exactly 0
    - k = n -> upper bound is exactly 1
    """
    if n <= 0:
        return (0.0, 1.0)
    p_hat = k / n
    z2 = _Z95 * _Z95
    denom = 1.0 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    margin = (_Z95 / denom) * math.sqrt(
        (p_hat * (1 - p_hat) / n) + (z2 / (4 * n * n))
    )
    return (max(0.0, center - margin), min(1.0, center + margin))


def brier_from_outcome(probability: float, resolved_binary: int | None) -> float | None:
    """Brier = (prob - outcome)^2. Returns None for ambiguous resolutions.

    We only compute Brier on binary resolutions (>=0.95 -> 1, <=0.05 -> 0). Mid-
    range resolutions don't map to a binary label, so Brier is undefined. See
    spec section "Metric definitions — which outcomes count".
    """
    if resolved_binary is None:
        return None
    return (probability - resolved_binary) ** 2


def simulated_pnl_eur(
    *, direction: str, probability: float, price_resolved: float, stake_eur: float = 10.0
) -> float:
    """Synthetic P&L with stake 10, zero fees, zero slippage.

    For BUY_YES: pnl = stake * (price_resolved - probability)
    For BUY_NO:  pnl = stake * (probability - price_resolved)

    Uses the RAW resolved price (float, not binary) so partial resolutions at
    e.g. 0.70 still produce a signed P&L number.
    """
    if direction == "BUY_YES":
        return stake_eur * (price_resolved - probability)
    # BUY_NO
    return stake_eur * (probability - price_resolved)
