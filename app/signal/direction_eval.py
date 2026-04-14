"""Map signal direction vs YES-token price moves (for outcome labels)."""


def price_moved_up(base: float, new: float) -> bool:
    return new > base


def direction_matches_price_move(direction: str, base: float, new: float) -> bool:
    """True if the observed move in YES price aligns with the signal direction."""
    d = (direction or "").upper()
    up = price_moved_up(base, new)
    if d in ("YES", "BUY_YES", "UP"):
        return up
    if d in ("NO", "BUY_NO", "DOWN"):
        return not up
    return False
