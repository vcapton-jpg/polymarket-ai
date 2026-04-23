"""build_detailed_sources and build_timeline map EventNewsLink → rich V2 shapes."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.signal_mapper import build_detailed_sources, build_timeline


def _mk_link(*, news_id, title, url, source_name, source_tier, source_weight,
             publish_date, key_excerpt, relevance_score):
    news = SimpleNamespace(
        id=news_id, title=title, url=url,
        source_name=source_name, source_tier=source_tier,
        source_weight=source_weight, publish_date=publish_date,
    )
    clean = SimpleNamespace(news=news)
    return SimpleNamespace(
        news_clean=clean,
        key_excerpt=key_excerpt,
        relevance_score=relevance_score,
    )


def test_detailed_sources_sorted_by_relevance_and_role_primary_is_top():
    t = datetime(2026, 4, 23, 12, 0, tzinfo=timezone.utc)
    links = [
        _mk_link(news_id=1, title="Low", url="u1", source_name="Blog",
                 source_tier=3, source_weight=0.4, publish_date=t,
                 key_excerpt="lo", relevance_score=0.3),
        _mk_link(news_id=2, title="High", url="u2", source_name="Reuters Top News",
                 source_tier=1, source_weight=0.95, publish_date=t,
                 key_excerpt="hi", relevance_score=0.9),
        _mk_link(news_id=3, title="Mid", url="u3", source_name="BBC News",
                 source_tier=1, source_weight=0.9, publish_date=t,
                 key_excerpt="md", relevance_score=0.6),
    ]
    out = build_detailed_sources(links)
    assert [s.newsId for s in out] == [2, 3, 1]
    assert out[0].role == "primary"
    assert out[1].role == "supporting"
    assert out[0].sourceTier == 1
    assert out[0].excerpt == "hi"
    assert out[0].relevanceScore == 0.9


def test_detailed_sources_handles_null_relevance_and_missing_news():
    orphan = SimpleNamespace(news_clean=None, key_excerpt=None, relevance_score=None)
    link_null_score = _mk_link(news_id=10, title="t", url="u",
                                source_name="X", source_tier=2,
                                source_weight=None, publish_date=None,
                                key_excerpt=None, relevance_score=None)
    out = build_detailed_sources([orphan, link_null_score])
    assert len(out) == 1
    assert out[0].newsId == 10
    assert out[0].relevanceScore is None
    assert out[0].publishDate is None


def test_timeline_sorts_desc_by_publish_date():
    t1 = datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 4, 22, 10, 0, tzinfo=timezone.utc)
    links = [
        _mk_link(news_id=1, title="early", url="u", source_name="A",
                 source_tier=2, source_weight=None, publish_date=t1,
                 key_excerpt=None, relevance_score=0.5),
        _mk_link(news_id=2, title="late", url="u", source_name="B",
                 source_tier=2, source_weight=None, publish_date=t2,
                 key_excerpt=None, relevance_score=0.5),
    ]
    out = build_timeline(links)
    assert [e.headline for e in out] == ["late", "early"]
    assert out[0].type == "news"
    assert out[0].source == "B"
