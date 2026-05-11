"""Map signal direction vs YES-token price moves (for outcome labels).

Two functions:
  * `direction_matches_price_move` (legacy, binary True/False) — keep for
    backward compat with any caller that explicitly needs a non-None bool.
  * `direction_correct_3state` (tri-state True/False/None) — preferred.
    Returns None when the price did not move (tie), so that aggregation
    queries (`WHERE direction_correct IS TRUE / IS FALSE`) can exclude
    ties from the denominator. The legacy function counted ties as
    "False" for BUY_YES and "True" for BUY_NO, which created an
    asymmetric labelling bias visible in the 30d audit (38 ties /
    5.4 % of resolutions at T+1h).
"""

from __future__ import annotations


def price_moved_up(base: float, new: float) -> bool:
    """Strict comparison — used by legacy callers. Ties → False."""
    return new > base


def direction_matches_price_move(direction: str, base: float, new: float) -> bool:
    """Legacy binary mapper. PREFER `direction_correct_3state` for new code.

    Ties (new == base) are returned as False for BUY_YES and as True for
    BUY_NO — that's the asymmetry we want to phase out.
    """
    d = (direction or "").upper()
    up = price_moved_up(base, new)
    if d in ("YES", "BUY_YES", "UP"):
        return up
    if d in ("NO", "BUY_NO", "DOWN"):
        return not up
    return False


def direction_correct_3state(
    direction: str, base: float, new: float
) -> bool | None:
    """Tri-state correct-flag : True / False / None (tie).

    When the YES-token price did not move strictly between snapshots
    (i.e. `new == base`), the trade outcome is **undecidable** at this
    horizon — there is no signed PnL. Returning None lets the SignalOutcome
    row carry a NULL `direction_correct`, which downstream aggregations
    already handle (`.is_(True)`, `.is_(False)`, `.is_not(None)` all
    exclude the NULLs from the count).

    Convention guarantees: a None tie at T+1h does NOT prevent the same
    signal from getting a non-None True/False at T+24h if the price moves
    later.
    """
    if base is None or new is None:
        return None
    if new == base:
        return None
    d = (direction or "").upper()
    up = new > base
    if d in ("YES", "BUY_YES", "UP"):
        return up
    if d in ("NO", "BUY_NO", "DOWN"):
        return not up
    return None
