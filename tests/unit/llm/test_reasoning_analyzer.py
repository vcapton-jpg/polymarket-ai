"""ReasoningAnalyzer — structured output, excerpt validation, tier-mix."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.llm.reasoning_analyzer import (
    ReasoningAnalyzer,
    compute_tier_mix,
    validate_output,
)


ARTICLES = [
    {
        "news_clean_id": 1,
        "title": "Reuters: Summit confirmed",
        "source_name": "Reuters Top News",
        "source_tier": 1,
        "clean_text": "Reuters reported today that the summit is confirmed for April 28.",
        "publish_date": "2026-04-23T14:03:00Z",
    },
    {
        "news_clean_id": 2,
        "title": "BBC: Officials agree",
        "source_name": "BBC News",
        "source_tier": 1,
        "clean_text": "BBC sources confirmed officials agreed on the date.",
        "publish_date": "2026-04-23T14:47:00Z",
    },
]


def test_compute_tier_mix_counts():
    mix = compute_tier_mix(ARTICLES)
    assert mix == {"tier_1": 2}


def test_validate_output_accepts_valid():
    out = {
        "impact_score": 0.7,
        "confidence": 0.8,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters reported the summit is confirmed for April 28, and BBC corroborates. "
            "This directly addresses the market resolution criteria. Convergence between "
            "Reuters Top News and BBC News raises conviction."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "officials agreed on the date", "relevance": 0.8},
        ],
    }
    errs, cleaned = validate_output(out, ARTICLES)
    assert errs == []
    assert len(cleaned["article_excerpts"]) == 2


def test_validate_output_rejects_short_reasoning():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": "Too short.",
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("reasoning" in e.lower() for e in errs)


def test_validate_output_rejects_reasoning_without_source_name():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": "x" * 120 + " Something that is long enough but never cites a registered source name.",
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("source name" in e.lower() for e in errs)


def test_validate_output_drops_non_substring_excerpts():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": (
            "Reuters Top News and BBC News both confirm the summit date, which addresses "
            "the market resolution criteria. Convergence raises conviction that the outcome lands YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "PARAPHRASED CONTENT NOT IN SOURCE", "relevance": 0.7},
        ],
    }
    errs, cleaned = validate_output(out, ARTICLES)
    assert errs == []
    assert len(cleaned["article_excerpts"]) == 1
    assert cleaned["article_excerpts"][0]["news_clean_id"] == 1


def test_validate_output_rejects_when_zero_valid_excerpts():
    out = {
        "impact_score": 0.7, "confidence": 0.8, "catalyst": "x",
        "reasoning": (
            "Reuters Top News and BBC News cover the story but none of the quoted "
            "phrases survive verification. The signal cannot be trusted without excerpts."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "paraphrased", "relevance": 0.9},
            {"news_clean_id": 2, "excerpt": "also paraphrased", "relevance": 0.8},
        ],
    }
    errs, _ = validate_output(out, ARTICLES)
    assert any("excerpt" in e.lower() for e in errs)


@pytest.mark.asyncio
async def test_analyze_parses_and_validates():
    analyzer = ReasoningAnalyzer()
    mock_resp = {
        "impact_score": 0.7,
        "confidence": 0.8,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters Top News reported the summit date, and BBC News corroborates the "
            "convergence. This addresses the market resolution criteria. Conviction is high."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "the summit is confirmed for April 28", "relevance": 0.9}
        ],
    }
    with patch.object(
        analyzer.client, "chat_completion",
        new=AsyncMock(return_value=json.dumps(mock_resp)),
    ):
        result = await analyzer.analyze(
            event_title="Summit",
            event_summary="Summit is happening",
            articles=ARTICLES,
            market_question="Will summit happen by May 1?",
            market_price=0.55,
        )
    assert result is not None
    assert result["reasoning"].startswith("Reuters")
    assert len(result["article_excerpts"]) == 1
    assert result["source_tier_mix"] == {"tier_1": 2}
