"""v1 composers must match the existing inline f-strings bit-exactly.

This is a regression shield: if this test fails, we have changed behavior
that would break the v1 baseline's comparison fidelity."""

from __future__ import annotations

import pytest

from app.processing.text_composers import (
    ComposedText,
    compose_event_v1,
    compose_market_v1,
    compose_news_v1,
)


# ── news v1 ──────────────────────────────────────────────────────────
def test_news_v1_matches_inline_fstring_pattern():
    # The inline prod path in tasks_pipeline.py:98 is: f"{raw_title}. {clean_text[:1500]}"
    title = "An Important Headline"
    body = "A" * 2000
    got = compose_news_v1(title, body)
    expected_text = f"{title}. {body[:1500]}"
    assert got.text == expected_text
    assert got.composition_version == "news_v1_title_trunc"


def test_news_v1_short_body_unchanged():
    got = compose_news_v1("T", "short body")
    assert got.text == "T. short body"


def test_news_v1_empty_body():
    got = compose_news_v1("T", "")
    assert got.text == "T. "


# ── market v1 ────────────────────────────────────────────────────────
def test_market_v1_matches_existing_build_retrieval_text():
    # Existing app.workers.tasks_ingestion._build_retrieval_text shape:
    # f"{question}. {desc_clean[:400]} {tags_str}".strip()
    # where desc_clean strips known boilerplate and collapses \n{2,} → \n.
    mkt = {
        "question": "Will X win?",
        "description": "Some description.",
        "tags": ["politics", "2028"],
    }
    got = compose_market_v1(mkt)
    # The body has no boilerplate, so desc_clean == description.
    expected = "Will X win?. Some description. politics 2028"
    assert got.text == expected
    assert got.composition_version == "market_v1_q_desc_tags"


def test_market_v1_strips_boilerplate_identical_to_legacy():
    # Known boilerplate we currently strip — give it some, verify it's gone.
    from app.workers.tasks_ingestion import _BOILERPLATE_RE
    # Craft a description containing a matched boilerplate token.
    boiler = "This market will resolve to YES." if _BOILERPLATE_RE.pattern else ""
    # The test matters only if the regex is non-empty. If it is, the output
    # must not include the boilerplate phrase.
    mkt = {"question": "q", "description": f"real content. {boiler}", "tags": []}
    got = compose_market_v1(mkt)
    if boiler:
        assert boiler not in got.text


def test_market_v1_empty_tags_and_description():
    got = compose_market_v1({"question": "q", "description": "", "tags": []})
    assert got.text == "q."


# ── event v1 ─────────────────────────────────────────────────────────
def test_event_v1_matches_canonical_format():
    # The authoritative shape (event_builder.py:56-58):
    # retrieval_parts = [event_title, event_summary[:300]]
    # retrieval_parts.extend(key_entities[:5])
    # event_retrieval_text = " ".join(retrieval_parts)
    got = compose_event_v1("Ev Title", "A summary here.", ["Alice", "Bob"])
    assert got.text == "Ev Title A summary here. Alice Bob"
    assert got.composition_version == "event_v1_title_summary_entities"


def test_event_v1_truncates_summary_at_300():
    long = "X" * 500
    got = compose_event_v1("T", long, [])
    assert got.text == f"T {long[:300]}".strip()


def test_event_v1_clips_entities_to_5():
    got = compose_event_v1("T", "s", ["a", "b", "c", "d", "e", "f", "g"])
    assert got.text.endswith("a b c d e")
