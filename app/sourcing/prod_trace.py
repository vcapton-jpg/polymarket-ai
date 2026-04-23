"""Audit writer for the production variant.

Production does NOT re-rank: it uses the articles the signal builder already
picked. We still need a row in `signal_articles` so "which 5 articles
generated this signal?" becomes one SQL query and so the shadow variant has a
prod comparison to join against.

No composite scoring happens here — `score`, `cosine_score`, `recency_weight`
are filled with 0.0 placeholders. If a future chantier wants to compare
rankings, it can re-score prod rows from the shadow side.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SignalArticle


async def record_prod_signal_articles(
    session: AsyncSession,
    *,
    signal_id: int,
    articles: list[dict[str, Any]],
) -> int:
    """Insert one SignalArticle row per article with variant='signal'.

    Rank is the 1-based index in the input list. Idempotent via ON CONFLICT
    DO NOTHING on the composite PK.

    Returns the count of rows actually inserted (0 when called a second time
    with identical args).
    """
    rows: list[dict[str, Any]] = []
    rank = 0
    for art in articles:
        ncid = art.get("news_clean_id")
        if ncid is None:
            continue
        rank += 1
        rows.append({
            "signal_id": signal_id,
            "variant": "signal",
            "news_clean_id": int(ncid),
            "rank": rank,
            "score": 0.0,
            "cosine_score": 0.0,
            "recency_weight": 0.0,
            "excerpt": art.get("excerpt"),
        })
    if not rows:
        return 0

    stmt = pg_insert(SignalArticle).values(rows).on_conflict_do_nothing(
        index_elements=["signal_id", "variant", "news_clean_id"]
    )
    result = await session.execute(stmt)
    return int(result.rowcount or 0)
