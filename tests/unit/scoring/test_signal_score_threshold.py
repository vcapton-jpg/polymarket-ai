"""Pin the signal_score_threshold default at 75 (winrate optimization Phase A).

Performance audit 2026-04-27 on 130 signals over a 3-day window:

| Score band | n   | T+1h hit | mean move 1h | T+24h hit | mean move 24h |
|------------|----:|----------|-------------:|-----------|--------------:|
| 75-89      |  37 | 47.2 %   |   +19.5 %    | 54.3 %    |   +21.3 %     |
| 60-74      |  73 | 37.5 %   |   -14.5 %    | 52.8 %    |    -2.8 %     |
| <60        |   4 | 25.0 %   |    -1.9 %    |  0.0 %    |    -7.9 %     |

The 60-74 band was generating the bulk of volume (56 %) with negative
expected returns. Raising the threshold to 75 strips that toxic band
from user-facing emission while preserving measurement data — sub-
threshold signals are still persisted with `_below_threshold=True` so
the `signal_predictions` aggregation continues to grow.

This file exists to ensure a future "default tweak" PR cannot quietly
revert the value below 75 without an explicit measurement-driven
justification.
"""
from __future__ import annotations

from app.core.config import Settings


def test_signal_score_threshold_field_default_is_at_least_75() -> None:
    """The threshold floor for user-facing signals.

    We test the FIELD default declared in the source, not the runtime
    `Settings()` instance — env-var overrides (set per environment in
    `.env`) are intentional and not the regression we guard against.
    The regression we DO guard against is a future commit silently
    lowering the source-code default below 75 without an updated audit.

    Raise the floor only if a fresh winrate audit shows a lower band
    has CI-disjoint positive expectancy. Lowering below 75 without that
    evidence is a regression — see the audit table in this module's
    docstring for the data behind the choice.
    """
    field = Settings.model_fields["signal_score_threshold"]
    assert field.default >= 75, (
        f"signal_score_threshold field default = {field.default} — "
        "winrate optimization Phase A (2026-04-27) pinned this at 75 "
        "because the 60-74 band had -14.5 % mean signed move at T+1h. "
        "Lowering the source-code default requires a fresh audit + "
        "CI-disjoint evidence."
    )


def test_signal_score_threshold_field_default_is_int_in_valid_range() -> None:
    """Defensive: type and range. The score itself is always 0-100."""
    field = Settings.model_fields["signal_score_threshold"]
    assert isinstance(field.default, int)
    assert 0 <= field.default <= 100
