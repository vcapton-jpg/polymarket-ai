"""Signal builder — reject if no reasoning or no valid excerpts; persist sources."""
from unittest.mock import AsyncMock

import pytest

from app.signal.signal_builder import build_signal


@pytest.mark.asyncio
async def test_rejects_when_reasoning_is_none():
    analyzer = AsyncMock()
    analyzer.analyze = AsyncMock(return_value=None)
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    result = await build_signal(
        event={"id": 1, "title": "t", "summary": "s"},
        market={"id": "m1", "question": "q?", "price": 0.5},
        articles=[{
            "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
            "source_tier": 1, "clean_text": "body", "publish_date": None,
        }],
        analyzer=analyzer,
        persist=False,
    )
    assert result is None


@pytest.mark.asyncio
async def test_persists_when_valid():
    analyzer = AsyncMock()
    analyzer.model_version = "gpt-4o-mini-2024-07-18"
    analyzer.analyze = AsyncMock(return_value={
        "impact_score": 0.8, "confidence": 0.9,
        "catalyst": "Summit confirmed",
        "reasoning": (
            "Reuters Top News confirms the summit, and this directly addresses the market "
            "resolution criteria. Convergence of reporting raises conviction. The direction is YES."
        ),
        "direction_recommendation": "YES",
        "article_excerpts": [
            {"news_clean_id": 1, "excerpt": "summit confirmed", "relevance": 0.9}
        ],
        "source_tier_mix": {"tier_1": 1},
    })
    result = await build_signal(
        event={"id": 1, "title": "t", "summary": "s"},
        market={"id": "m1", "question": "q?", "price": 0.5},
        articles=[{
            "news_clean_id": 1, "title": "x", "source_name": "Reuters Top News",
            "source_tier": 1, "clean_text": "summit confirmed today", "publish_date": None,
        }],
        analyzer=analyzer,
        persist=False,
    )
    assert result is not None
    assert result["reasoning"].startswith("Reuters")
    assert result["source_tier_mix"] == {"tier_1": 1}
    assert result["llm_model_version"] == "gpt-4o-mini-2024-07-18"
    assert len(result["article_excerpts"]) == 1
