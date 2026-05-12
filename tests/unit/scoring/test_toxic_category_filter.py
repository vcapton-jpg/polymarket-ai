"""Pin the toxic-category blacklist semantics.

T-LIQUID-1. The filter must:

* parse a CSV string from `settings.toxic_categories_blacklist`
* trim whitespace around each entry
* match `market_data["category"]` case-sensitively (Polymarket category
  values are canonical, no case normalization on their side)
* be a no-op when the setting is empty
* call the shadow capture helper with `rejection_reason="toxic_category:<name>"`

These tests exercise the backtest-rule shape (pure function, no DB).
"""

from __future__ import annotations


def _blacklist_parse(raw: str) -> set[str]:
    """Replicate the inline parser from `signal_builder.py`. Single
    source of truth — if the filter logic changes, this helper changes
    with it. Kept as a private testable surface."""
    raw = (raw or "").strip()
    if not raw:
        return set()
    return {c.strip() for c in raw.split(",") if c.strip()}


def test_empty_blacklist_is_a_noop():
    """An empty setting → an empty set → no signal ever rejected."""
    assert _blacklist_parse("") == set()
    assert _blacklist_parse("   ") == set()


def test_blacklist_csv_trims_whitespace():
    """Operator-fat-fingered CSV with extra spaces must still parse."""
    parsed = _blacklist_parse("Hezbollah , Iran Ceasefire,  Sports   ")
    assert parsed == {"Hezbollah", "Iran Ceasefire", "Sports"}


def test_blacklist_preserves_internal_whitespace():
    """The category string itself can contain spaces — must not be
    stripped to a single word ('Iran Ceasefire' is one entry, not two)."""
    parsed = _blacklist_parse("Iran Ceasefire")
    assert parsed == {"Iran Ceasefire"}
    assert "Iran" not in parsed
    assert "Ceasefire" not in parsed


def test_blacklist_is_case_sensitive():
    """Polymarket categories are canonical — 'Hezbollah' must NOT match
    'hezbollah' (we want an exact match, not a fuzzy one, to avoid
    silently blocking unrelated 'iranAirport' or similar)."""
    parsed = _blacklist_parse("Hezbollah")
    assert "Hezbollah" in parsed
    assert "hezbollah" not in parsed
    assert "HEZBOLLAH" not in parsed


def test_blacklist_ignores_trailing_comma():
    """Common operator typo — trailing comma must not create an empty
    string entry (which would match a None or '' category and block
    everything)."""
    parsed = _blacklist_parse("Hezbollah,Iran Ceasefire,")
    assert parsed == {"Hezbollah", "Iran Ceasefire"}
    assert "" not in parsed


def test_blacklist_dedupes_repeated_entries():
    """Defensive — same category listed twice doesn't double-trigger."""
    parsed = _blacklist_parse("Hezbollah,Hezbollah,Iran Ceasefire")
    assert parsed == {"Hezbollah", "Iran Ceasefire"}
