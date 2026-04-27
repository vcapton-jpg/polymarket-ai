"""Pin the two end-to-end freshness thresholds at ≤ 2h.

After the 2026-04-27 lag audit on X tweets ingested via RSSHub, both
the ingestion gate (`rss_max_article_age_hours`) and the event scoring
gate (`signal_event_max_age_hours`) were tightened to 2.0. The tests
guard the source-code default — env-var overrides remain valid for
operators who want to relax temporarily, but the source-of-truth must
not drift back upward without measured justification.
"""
from __future__ import annotations

from app.core.config import Settings


def test_rss_max_article_age_hours_default_is_at_most_2() -> None:
    field = Settings.model_fields["rss_max_article_age_hours"]
    assert field.default <= 2.0, (
        f"rss_max_article_age_hours field default = {field.default}h — "
        "the 2026-04-27 lag audit pinned this at 2h because tweets older "
        "than 2h have lost their Polymarket-pricing edge. Loosening the "
        "source-code default requires a fresh measurement of mean signed "
        "move at T+1h vs article age."
    )


def test_signal_event_max_age_hours_default_is_at_most_2() -> None:
    field = Settings.model_fields["signal_event_max_age_hours"]
    assert field.default <= 2.0, (
        f"signal_event_max_age_hours field default = {field.default}h — "
        "kept aligned with rss_max_article_age_hours so the freshness "
        "chain is consistent end-to-end. Loosening one without the other "
        "creates a window where stale articles slip past ingestion and "
        "still get scored."
    )


def test_freshness_thresholds_are_aligned() -> None:
    """The two thresholds gate the same staleness concern at two
    different stages. They must move together — diverging values open
    a gap where tweets just-too-old-for-ingestion still produce events
    that pass the scoring gate.
    """
    rss = Settings.model_fields["rss_max_article_age_hours"].default
    sig = Settings.model_fields["signal_event_max_age_hours"].default
    assert rss == sig, (
        f"rss_max_article_age_hours ({rss}h) ≠ signal_event_max_age_hours "
        f"({sig}h). The end-to-end staleness budget must be a single number "
        "— diverging lets stale articles slip through the chain."
    )
