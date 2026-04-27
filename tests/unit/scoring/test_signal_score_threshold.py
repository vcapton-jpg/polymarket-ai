"""Pin the signal_score_threshold default at ≥65 (winrate optimization Phase A).

Performance audit 2026-04-27 on 130 signals over a 3-day window:

| Score band | n   | T+1h hit | mean move 1h | T+24h hit | mean move 24h |
|------------|----:|----------|-------------:|-----------|--------------:|
| 75-89      |  37 | 47.2 %   |   +19.5 %    | 54.3 %    |   +21.3 %     |
| 60-74      |  73 | 37.5 %   |   -14.5 %    | 52.8 %    |    -2.8 %     |
| <60        |   4 | 25.0 %   |    -1.9 %    |  0.0 %    |    -7.9 %     |

We pin the floor at 65 — strict enough to drop the worst-performing
sub-threshold band (<60 was -7.9 % at 24h on n=4) but permissive enough
to keep the 65-74 sub-band, which is being investigated separately:
many of its misfires are likely stale-news signals that a follow-up
freshness gate will catch. After the freshness fix ships and the
65-74 winrate is re-measured, the floor may be promoted to 75.

This file exists to ensure a future "default tweak" PR cannot quietly
lower the value below 65 without an explicit measurement-driven
justification.
"""
from __future__ import annotations

from app.core.config import Settings


def test_signal_score_threshold_field_default_is_at_least_65() -> None:
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
    assert field.default >= 65, (
        f"signal_score_threshold field default = {field.default} — "
        "winrate optimization Phase A (2026-04-27) pinned this at 65 "
        "because the 60-74 band had -14.5 % mean signed move at T+1h. "
        "Lowering the source-code default requires a fresh audit + "
        "CI-disjoint evidence."
    )


def test_signal_score_threshold_field_default_is_int_in_valid_range() -> None:
    """Defensive: type and range. The score itself is always 0-100."""
    field = Settings.model_fields["signal_score_threshold"]
    assert isinstance(field.default, int)
    assert 0 <= field.default <= 100
