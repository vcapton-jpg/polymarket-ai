"""Eval-pair loaders for the embedding harness.

Three sources, merged and deduped by load_pairs():
- db_heuristic   — from existing DB links (cheap, circular-ish)
- downstream_pnl — only event_to_market; positive pairs validated by real outcomes
- llm_judge      — cached GPT-4o-mini relevance judgments, hard-capped $ budget

This task (task 4) ships only `db_heuristic` + the public `load_pairs` dispatcher.
The other two sources land in task 5.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    EventMarketAnalysis,
    EventMarketCandidate,
    EventNewsLink,
    Signal,
    SignalArticle,
)


Surface = Literal["event_to_market", "article_to_event", "market_to_article"]
_VALID_SURFACES = ("event_to_market", "article_to_event", "market_to_article")


@dataclass(frozen=True)
class EvalPair:
    query_id: int | str
    relevant_ids: frozenset[int | str]
    source: str               # "db_heuristic" | "downstream_pnl" | "llm_judge"
    surface: str              # one of Surface values above


async def load_pairs(session: AsyncSession, *, surface: str, limit: int = 500) -> list[EvalPair]:
    """Public entry point. Aggregates all applicable sources for `surface`
    and dedupes by (query_id, frozenset(relevant_ids)) keeping the noblest source.

    Source nobility order: downstream_pnl > llm_judge > db_heuristic.
    """
    if surface not in _VALID_SURFACES:
        raise ValueError(f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}")

    nobility = {"downstream_pnl": 2, "llm_judge": 1, "db_heuristic": 0}
    aggregated: dict[tuple[int | str, frozenset], EvalPair] = {}

    def _accept(pair: EvalPair) -> None:
        key = (pair.query_id, pair.relevant_ids)
        current = aggregated.get(key)
        if current is None or nobility[pair.source] > nobility[current.source]:
            aggregated[key] = pair

    for p in await _load_db_heuristic(session, surface, limit):
        _accept(p)
    for p in await _load_downstream_pnl(session, surface):
        _accept(p)
    db_pairs = list(aggregated.values())
    for p in await _load_llm_judge(session, surface, db_pairs, n_candidates=200):
        _accept(p)

    return list(aggregated.values())


async def _load_db_heuristic(
    session: AsyncSession, surface: str, limit: int
) -> list[EvalPair]:
    if surface == "event_to_market":
        return await _db_event_to_market(session, limit)
    if surface == "article_to_event":
        return await _db_article_to_event(session, limit)
    if surface == "market_to_article":
        return await _db_market_to_article(session, limit)
    return []


async def _db_event_to_market(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (event_id, market_id) if the candidate was ranked <= 3 AND an
    EventMarketAnalysis row exists for it (LLM #2 considered it worth analyzing)."""
    stmt = (
        select(
            EventMarketCandidate.event_id,
            EventMarketCandidate.market_id,
        )
        .join(
            EventMarketAnalysis,
            (EventMarketAnalysis.event_id == EventMarketCandidate.event_id)
            & (EventMarketAnalysis.market_id == EventMarketCandidate.market_id),
        )
        .where(EventMarketCandidate.rank <= 3)
        .where(EventMarketAnalysis.impact_strength.isnot(None))
        .order_by(EventMarketCandidate.event_id.desc())
        .limit(limit * 5)  # one event may have multiple markets; over-sample
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[str]] = {}
    for event_id, market_id in rows:
        grouped.setdefault(event_id, set()).add(market_id)
    pairs = [
        EvalPair(
            query_id=eid,
            relevant_ids=frozenset(mids),
            source="db_heuristic",
            surface="event_to_market",
        )
        for eid, mids in grouped.items()
    ]
    return pairs[:limit]


async def _db_article_to_event(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (clean_id, event_id) if role='primary'."""
    stmt = (
        select(EventNewsLink.clean_id, EventNewsLink.event_id)
        .where(EventNewsLink.role == "primary")
        .order_by(EventNewsLink.clean_id.desc())
        .limit(limit * 3)
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[int]] = {}
    for clean_id, event_id in rows:
        grouped.setdefault(clean_id, set()).add(event_id)
    pairs = [
        EvalPair(
            query_id=cid,
            relevant_ids=frozenset(eids),
            source="db_heuristic",
            surface="article_to_event",
        )
        for cid, eids in grouped.items()
    ]
    return pairs[:limit]


async def _db_market_to_article(session: AsyncSession, limit: int) -> list[EvalPair]:
    """Positive (market_id, clean_id) if SignalArticle.variant='signal' AND rank <= 5.
    We group by market_id (derived via Signal.market_id — joined through the FK).
    """
    stmt = (
        select(Signal.market_id, SignalArticle.news_clean_id)
        .join(Signal, Signal.id == SignalArticle.signal_id)
        .where(SignalArticle.variant == "signal")
        .where(SignalArticle.rank <= 5)
        .order_by(SignalArticle.signal_id.desc())
        .limit(limit * 5)
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[str, set[int]] = {}
    for market_id, clean_id in rows:
        grouped.setdefault(market_id, set()).add(clean_id)
    pairs = [
        EvalPair(
            query_id=mid,
            relevant_ids=frozenset(cids),
            source="db_heuristic",
            surface="market_to_article",
        )
        for mid, cids in grouped.items()
    ]
    return pairs[:limit]


# ══════════════════════════════════════════════════════════════════════
# Downstream P&L source — only event_to_market
# ══════════════════════════════════════════════════════════════════════

async def _load_downstream_pnl(session: AsyncSession, surface: str) -> list[EvalPair]:
    """Only applies to event_to_market. A pair is positive if a real signal on
    (event, market) resolved profitably in the production variant.

    Chantier #5: the production variant was renamed from 'signal' to
    'heuristic_v1' by migration 025. This filter follows that rename.
    """
    if surface != "event_to_market":
        return []
    from app.db.models import SignalPrediction
    stmt = (
        select(Signal.event_id, Signal.market_id)
        .join(SignalPrediction, SignalPrediction.signal_id == Signal.id)
        .where(SignalPrediction.variant == "heuristic_v1")
        .where(SignalPrediction.direction_correct.is_(True))
        .where(SignalPrediction.simulated_pnl_eur > 0)
        .where(Signal.event_id.isnot(None))
    )
    rows = (await session.execute(stmt)).all()
    grouped: dict[int, set[str]] = {}
    for event_id, market_id in rows:
        grouped.setdefault(event_id, set()).add(market_id)
    return [
        EvalPair(
            query_id=eid,
            relevant_ids=frozenset(mids),
            source="downstream_pnl",
            surface="event_to_market",
        )
        for eid, mids in grouped.items()
    ]


# ══════════════════════════════════════════════════════════════════════
# LLM-judge source — cached, budget-capped
# ══════════════════════════════════════════════════════════════════════

import hashlib
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LLM_JUDGE_CACHE_DIR = Path(".eval_cache")
_LLM_JUDGE_MODEL = "gpt-4o-mini"
# Rough estimate — updated if real token counts differ.
_LLM_JUDGE_COST_PER_CALL_USD = 0.0002


async def _llm_judge_prompt_one_pair(
    *, query_text: str, target_text: str, surface: str
) -> dict:
    """One LLM call. Isolated so tests can monkeypatch it.
    Returns a dict with {"relevance": "yes" | "no" | "unclear"}."""
    from openai import AsyncOpenAI
    from app.core.config import get_settings

    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    prompt = (
        "You are judging topical relevance for a prediction-market retrieval system.\n\n"
        f"Surface: {surface}\n"
        f"Query: {query_text[:800]}\n"
        f"Candidate: {target_text[:800]}\n\n"
        "Is the candidate topically relevant to the query? "
        "Answer with a single word: yes, no, or unclear."
    )
    resp = await client.chat.completions.create(
        model=_LLM_JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=5,
        temperature=0.0,
    )
    raw = (resp.choices[0].message.content or "").strip().lower()
    verdict = "unclear"
    if raw.startswith("yes"):
        verdict = "yes"
    elif raw.startswith("no"):
        verdict = "no"
    return {"relevance": verdict}


async def _load_llm_judge(
    session: AsyncSession,
    surface: str,
    existing_pairs: list[EvalPair],
    n_candidates: int = 200,
) -> list[EvalPair]:
    """Sample ≤ n_candidates (query, target) pairs for `surface`, judge each
    via LLM, return pairs where the verdict is 'yes'. Cached on disk."""
    from app.core.config import get_settings
    settings = get_settings()
    budget_usd = float(settings.llm_judge_max_usd)
    if budget_usd <= 0.0:
        logger.info("LLM judge: budget_usd=0, skipping")
        return []

    _LLM_JUDGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _LLM_JUDGE_CACHE_DIR / f"llm_judge_{surface}.json"
    cache: dict[str, str] = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text())
        except json.JSONDecodeError:
            logger.warning("LLM judge cache corrupt at %s, starting fresh", cache_file)
            cache = {}

    # Candidate pairs: half positives (rotate existing), half random negatives.
    # For this first cut we pull candidates from `existing_pairs` and pair them
    # with random other rows — keeps the loader surface-agnostic.
    from random import Random
    rng = Random(42)
    positives = list(existing_pairs)[: n_candidates // 2]
    candidates: list[tuple[int | str, int | str]] = []
    for p in positives:
        for r in p.relevant_ids:
            candidates.append((p.query_id, r))  # true positive candidate
            # Negative: pick a query_id from another pair's relevants.
            others = [q.relevant_ids for q in existing_pairs if q.query_id != p.query_id]
            if others:
                neg_pool = list(next(iter(rng.choice(others))) for _ in range(1))
                if neg_pool:
                    candidates.append((p.query_id, rng.choice(neg_pool)))

    if not candidates:
        return []
    candidates = candidates[:n_candidates]

    # Load query & target texts once to keep I/O tight.
    qtexts: dict[int | str, str] = await _fetch_texts_for_keys(
        session, surface, keys=list({c[0] for c in candidates}), side="query"
    )
    ttexts: dict[int | str, str] = await _fetch_texts_for_keys(
        session, surface, keys=list({c[1] for c in candidates}), side="target"
    )

    calls_budget = int(budget_usd / _LLM_JUDGE_COST_PER_CALL_USD)
    calls_used = 0
    positive_hits: dict[int | str, set[int | str]] = {}
    for qid, tid in candidates:
        key = hashlib.sha256(f"{surface}|{qid}|{tid}".encode()).hexdigest()[:32]
        if key in cache:
            verdict = cache[key]
        else:
            if calls_used >= calls_budget:
                logger.info("LLM judge: budget exhausted after %d calls", calls_used)
                break
            qtext = qtexts.get(qid, "")
            ttext = ttexts.get(tid, "")
            if not qtext or not ttext:
                continue
            res = await _llm_judge_prompt_one_pair(
                query_text=qtext, target_text=ttext, surface=surface
            )
            verdict = res.get("relevance", "unclear")
            cache[key] = verdict
            calls_used += 1
        if verdict == "yes":
            positive_hits.setdefault(qid, set()).add(tid)

    cache_file.write_text(json.dumps(cache, indent=2))
    logger.info(
        "LLM judge: %d calls used, $%.4f estimated, %d positive pairs cached",
        calls_used, calls_used * _LLM_JUDGE_COST_PER_CALL_USD, len(positive_hits),
    )

    return [
        EvalPair(
            query_id=qid,
            relevant_ids=frozenset(tids),
            source="llm_judge",
            surface=surface,
        )
        for qid, tids in positive_hits.items()
    ]


async def _fetch_texts_for_keys(
    session: AsyncSession, surface: str, keys: list, side: str
) -> dict:
    """Map key -> text for either the query or the target side of a surface."""
    from app.db.models import Event, Market, NewsClean
    if not keys:
        return {}
    if surface == "event_to_market":
        if side == "query":
            rows = (await session.execute(
                select(Event.id, Event.event_retrieval_text, Event.event_title)
                .where(Event.id.in_(keys))
            )).all()
            return {i: (t or tt or "") for (i, t, tt) in rows}
        rows = (await session.execute(
            select(Market.market_id, Market.market_retrieval_text, Market.question)
            .where(Market.market_id.in_(keys))
        )).all()
        return {i: (t or q or "") for (i, t, q) in rows}
    if surface == "article_to_event":
        if side == "query":
            rows = (await session.execute(
                select(NewsClean.id, NewsClean.clean_text)
                .where(NewsClean.id.in_(keys))
            )).all()
            return {i: (t or "") for (i, t) in rows}
        rows = (await session.execute(
            select(Event.id, Event.event_retrieval_text, Event.event_title)
            .where(Event.id.in_(keys))
        )).all()
        return {i: (t or tt or "") for (i, t, tt) in rows}
    # market_to_article
    if side == "query":
        rows = (await session.execute(
            select(Market.market_id, Market.market_retrieval_text, Market.question)
            .where(Market.market_id.in_(keys))
        )).all()
        return {i: (t or q or "") for (i, t, q) in rows}
    rows = (await session.execute(
        select(NewsClean.id, NewsClean.clean_text)
        .where(NewsClean.id.in_(keys))
    )).all()
    return {i: (t or "") for (i, t) in rows}
