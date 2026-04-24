"""Tests for v2 composers — one file per task (A1/A3/A4), appended as we go."""

from __future__ import annotations

import pytest

from app.processing.text_composers import compose_news_v2


# ── A1: news v2 ──────────────────────────────────────────────────────
def test_news_v2_composition_version_is_stable():
    got = compose_news_v2("T", "a body")
    assert got.composition_version == "news_v2_lead_tail"


def test_news_v2_no_paragraphs_falls_back_to_truncation():
    body = "single-line body no paragraph breaks " * 200  # >1500 chars, no \n\n
    got = compose_news_v2("T", body)
    # Fallback path: title + body[:1500], total <= 1800 chars.
    assert got.text.startswith("T.")
    assert len(got.text) <= 1800


def test_news_v2_short_single_paragraph_uses_it_as_is():
    body = "This is a single short paragraph roughly under 100 chars... oh wait, this is actually longer."
    got = compose_news_v2("T", body)
    assert body in got.text or body[:1200] in got.text


def test_news_v2_multi_paragraph_keeps_lead_and_tail():
    lead = "LEAD CONTENT. " * 20   # ~280 chars — meets ≥ 80 filter
    middle = "MIDDLE CONTENT. " * 30
    tail = "FINAL TAKEAWAY. " * 10  # ~160 chars
    body = f"{lead}\n\n{middle}\n\n{tail}"
    got = compose_news_v2("Title", body)
    # Both lead start and tail start should survive.
    assert "LEAD CONTENT." in got.text
    assert "FINAL TAKEAWAY." in got.text
    # Total length cap.
    assert len(got.text) <= 1800


def test_news_v2_only_short_paragraphs_falls_back():
    # Paragraphs < 80 chars are filtered out; falls back to truncation.
    body = "short\n\nalso short\n\nstill short"
    got = compose_news_v2("T", body)
    # Fallback: title + body[:1500].
    assert got.text.startswith("T.")


def test_news_v2_total_length_capped_at_1800():
    long_lead = "X" * 5000
    long_tail = "Y" * 5000
    body = f"{long_lead}\n\n{long_tail}"
    got = compose_news_v2("T", body)
    assert len(got.text) <= 1800


def test_news_v2_empty_body():
    got = compose_news_v2("T", "")
    # Nothing meaningful to do; should not crash and output should be well-formed.
    assert got.text.startswith("T")


# ── A3: market v2 ────────────────────────────────────────────────────
from app.processing.text_composers import compose_market_v2


def test_market_v2_composition_version_is_stable():
    got = compose_market_v2({"question": "q", "description": "d", "tags": [], "category": "Politics"})
    assert got.composition_version == "market_v2_with_category"


def test_market_v2_with_category_injects_bracket_marker():
    mkt = {
        "question": "Will X win?",
        "description": "Context here.",
        "tags": ["politics", "2028"],
        "category": "Politics",
    }
    got = compose_market_v2(mkt)
    assert "[category: Politics]" in got.text
    # Preserves question and tags.
    assert got.text.startswith("Will X win?.")
    assert "politics 2028" in got.text


def test_market_v2_without_category_omits_bracket():
    mkt = {"question": "q", "description": "", "tags": [], "category": None}
    got = compose_market_v2(mkt)
    assert "[category:" not in got.text


def test_market_v2_empty_category_treated_as_absent():
    mkt = {"question": "q", "description": "", "tags": [], "category": ""}
    got = compose_market_v2(mkt)
    assert "[category:" not in got.text


def test_market_v2_strips_boilerplate_same_as_v1():
    mkt = {
        "question": "q",
        "description": "real content\n\n\nstill here.",
        "tags": [],
        "category": "X",
    }
    got = compose_market_v2(mkt)
    # \n{2,} → \n collapse matches v1 behavior.
    assert "\n\n\n" not in got.text
