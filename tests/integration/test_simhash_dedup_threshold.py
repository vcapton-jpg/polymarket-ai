"""Characterize current simhash dedup behaviour at the live threshold.

Originally intended (chantier-2 plan v1) as a TDD net to drive lowering
`clustering_simhash_threshold` from 0.15 to 0.05. **Empirical investigation
(2026-04-25) found that hypothesis wrong:** the minimum cross-outlet
Hamming distance in 800 rows of prod NewsClean is 15 bits, with the bulk
at 22-25 bits — i.e. the 9-bit gate (0.15 * 64 floored at 3) essentially
never fires on cross-outlet pairs. Lowering the threshold would not
change clustering inventory.

Pinning the live behaviour anyway so a future regression that makes
dedup over-aggressive (or that disables it entirely) gets caught.

Bug 1 in the chantier-2 audit doc is therefore retracted; the real cause
of 99% single-source events is upstream cosine clustering — see notes in
`docs/superpowers/plans/2026-04-25-clustering-hardening.md` §"Empirical
findings" appendix.
"""

from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import News, NewsClean
from app.workers.tasks_pipeline import _check_simhash_dup, _compute_simhash


def _hamming(a: int, b: int) -> int:
    # Normalize to the unsigned 64-bit space the dedup logic uses; Python ints
    # are arbitrary-precision so a raw XOR can yield a negative if signs differ.
    return bin((a ^ b) & ((1 << 64) - 1)).count("1")


@pytest.mark.asyncio
async def test_distinct_stories_not_deduped(async_db_factory):
    """Two articles, different topics — must NOT be marked as duplicates.

    Sanity that the dedup at the live threshold doesn't false-positive.
    Hamming on these inputs is ~30 bits in practice, well above any
    reasonable threshold.
    """
    URLS = ["https://example.com/sim-distinct-1", "https://example.com/sim-distinct-2"]
    text_a = (
        "Federal Reserve raises interest rates by 25 basis points in "
        "March meeting, citing persistent inflation pressures"
    )
    text_b = (
        "The Fed announced a quarter-point hike Wednesday, bringing "
        "benchmark borrowing costs to a 23-year high amid sticky CPI"
    )
    sh_a, sh_b = _compute_simhash(text_a), _compute_simhash(text_b)
    # Sanity — these texts ARE far apart at the simhash level (we're not
    # testing a degenerate near-duplicate case).
    assert _hamming(sh_a, sh_b) > 10, (
        f"test inputs unexpectedly similar (hamming={_hamming(sh_a, sh_b)})"
    )

    async with async_db_factory() as s:
        n_a = News(
            url=URLS[0], title="a", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add(n_a)
        await s.flush()
        s.add(NewsClean(news_id=n_a.id, clean_text=text_a, simhash=sh_a))
        await s.commit()

    try:
        async with async_db_factory() as s:
            is_dup = await _check_simhash_dup(
                s, simhash_val=sh_b,
                threshold=get_settings().clustering_simhash_threshold,
            )
            assert is_dup is False, (
                "distinct story marked as duplicate — threshold became "
                "permissive enough to false-positive on unrelated stories"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.in_(URLS))))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.commit()


@pytest.mark.asyncio
async def test_near_identical_wire_syndication_still_deduped(async_db_factory):
    """A literal copy of a Reuters wire republished elsewhere must STILL
    be deduped — wire syndication would otherwise inflate
    unique_sources_count artificially."""
    URLS = ["https://example.com/sim-wire-1", "https://example.com/sim-wire-2"]
    text = (
        "WASHINGTON (Reuters) - The U.S. Treasury on Friday imposed "
        "sanctions on three companies linked to alleged sanctions evasion."
    )
    sh = _compute_simhash(text)

    async with async_db_factory() as s:
        n = News(
            url=URLS[0], title="reuters", source_name="reuters",
            source_tier=1, source_weight=0.95,
        )
        s.add(n)
        await s.flush()
        s.add(NewsClean(news_id=n.id, clean_text=text, simhash=sh))
        await s.commit()

    try:
        async with async_db_factory() as s:
            is_dup = await _check_simhash_dup(
                s, simhash_val=sh,
                threshold=get_settings().clustering_simhash_threshold,
            )
            assert is_dup is True, (
                "wire syndication leaked through — threshold so tight "
                "that exact-text reposts no longer count as duplicates"
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(NewsClean).where(NewsClean.news.has(News.url.in_(URLS))))
            await s.execute(delete(News).where(News.url.in_(URLS)))
            await s.commit()
