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
    and dedupes by (query_id, frozenset(relevant_ids)) keeping the noblest source."""
    if surface not in _VALID_SURFACES:
        raise ValueError(f"Unknown surface {surface!r}; must be one of {_VALID_SURFACES}")

    aggregated: dict[tuple[int | str, frozenset], EvalPair] = {}

    for pair in await _load_db_heuristic(session, surface, limit):
        key = (pair.query_id, pair.relevant_ids)
        aggregated[key] = pair

    # Sources 2 and 3 are wired in task 5; they slot in here with source-noblest
    # tie-breaking (downstream_pnl > llm_judge > db_heuristic).

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
