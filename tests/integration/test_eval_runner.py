"""End-to-end eval on a tiny fixture — covers task 6."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from app.db.models import Event, EventMarketAnalysis, EventMarketCandidate, Market
from app.eval.runner import run_eval, diff_reports, report_to_json
from tests.helpers.embedding_fixtures import make_toy_embedding


NOW = datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _no_llm_judge(monkeypatch):
    """Stop load_pairs() from calling real OpenAI during runner tests."""
    from app.eval import labels as labels_module

    async def _fake(**_kw):
        return {"relevance": "unclear"}

    monkeypatch.setattr(labels_module, "_llm_judge_prompt_one_pair", _fake)


@pytest.fixture
async def runner_corpus(async_db_factory):
    async with async_db_factory() as s:
        ev = Event(
            id=4001, event_title="ev-r", first_seen=NOW, last_seen=NOW, bucket="politics",
            embedding=make_toy_embedding(axis=0),
            embedding_v2=make_toy_embedding(axis=1),
        )
        # 3 markets: m_good points along axis 0 (matches v1 query), m_good2 along axis 1 (matches v2), m_bad unrelated.
        m_good = Market(
            market_id="m_good", question="q", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=0),
            embedding_v2=make_toy_embedding(axis=0),
        )
        m_good2 = Market(
            market_id="m_good2", question="q2", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=2),
            embedding_v2=make_toy_embedding(axis=1),
        )
        m_bad = Market(
            market_id="m_bad", question="q3", active=True, closed=False,
            accepting_orders=True, bucket="politics",
            embedding=make_toy_embedding(axis=5),
            embedding_v2=make_toy_embedding(axis=5),
        )
        s.add_all([ev, m_good, m_good2, m_bad])
        await s.flush()
        s.add_all([
            EventMarketCandidate(event_id=4001, market_id="m_good", rank=1, cosine_score=0.9, rrf_score=0.9),
            EventMarketCandidate(event_id=4001, market_id="m_good2", rank=2, cosine_score=0.8, rrf_score=0.8),
            EventMarketAnalysis(event_id=4001, market_id="m_good", impact_strength=0.8),
            EventMarketAnalysis(event_id=4001, market_id="m_good2", impact_strength=0.6),
        ])
        await s.commit()

    yield

    async with async_db_factory() as s:
        await s.execute(delete(EventMarketAnalysis).where(EventMarketAnalysis.event_id == 4001))
        await s.execute(delete(EventMarketCandidate).where(EventMarketCandidate.event_id == 4001))
        await s.execute(delete(Market).where(Market.market_id.in_(["m_good", "m_good2", "m_bad"])))
        await s.execute(delete(Event).where(Event.id == 4001))
        await s.commit()


async def test_run_eval_v1_ranks_axis0_market_first(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        report = await run_eval(s, variant="v1", surface="event")
    # v1 query (axis 0) matches m_good (axis 0) perfectly → retrieval@5 hit on m_good.
    assert report.n_pairs >= 1
    assert report.metrics["retrieval@5"]["mean"] > 0.0


async def test_run_eval_v2_report_has_n_skipped_zero_when_v2_populated(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        report = await run_eval(s, variant="v2", surface="event")
    assert report.n_skipped == 0


async def test_report_to_json_roundtrips(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        r = await run_eval(s, variant="v1", surface="event")
    import json
    payload = report_to_json(r)
    parsed = json.loads(payload)
    assert parsed["variant"] == "v1"
    assert parsed["surface"] == "event"
    assert "retrieval@5" in parsed["metrics"]


async def test_diff_reports_flags_per_metric_gain(runner_corpus, async_db_factory):
    async with async_db_factory() as s:
        r1 = await run_eval(s, variant="v1", surface="event")
        r2 = await run_eval(s, variant="v2", surface="event")
    d = diff_reports(r1, r2)
    assert "retrieval@5" in d
    assert "delta" in d["retrieval@5"]
    assert "verdict" in d["retrieval@5"]
    assert d["retrieval@5"]["verdict"] in ("improved", "regressed", "flat")
