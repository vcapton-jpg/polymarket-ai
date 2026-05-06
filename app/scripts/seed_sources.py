"""Seed sources_registry with Blueprint V4 Tier 1/2/3 sources."""

import asyncio

from sqlalchemy import select

from app.db.database import async_session_factory
from app.db.models import SourceRegistry

RSSHUB = "https://rsshub.app/twitter/user"

SOURCES = [
    # ══════════════════════════════════════════════════════════════════
    # Tier 1 — Agency RSS feeds (< 30 s)
    # ══════════════════════════════════════════════════════════════════
    # NOTE on Reuters/AP feeds: feeds.reuters.com and feeds.apnews.com were
    # retired by the publishers (Reuters in 2020, AP shortly after) — DNS
    # no longer resolves, so we use Google News query feeds as the primary
    # path. Tested 2026-05-06: each returns ~100 fresh items per fetch.
    # The X (Twitter) variants below remain as redundant secondary path
    # for when TWITTER_AUTH_TOKEN is rotated and RSSHub Twitter is healthy.
    {"source_name": "Reuters via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Reuters+breaking", "tier": 1, "weight": 1.0},
    {"source_name": "Reuters World via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Reuters+world", "tier": 1, "weight": 1.0},
    {"source_name": "AP via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Associated+Press+breaking", "tier": 1, "weight": 1.0},
    {"source_name": "Bloomberg via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Bloomberg+breaking", "tier": 1, "weight": 1.0},
    {"source_name": "FT via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Financial+Times+breaking", "tier": 1, "weight": 0.95},
    {"source_name": "WSJ via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Wall+Street+Journal+breaking", "tier": 1, "weight": 0.95},
    {"source_name": "Politico via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=Politico+breaking", "tier": 1, "weight": 0.90},
    {"source_name": "BBC World", "source_type": "rss", "url": "https://feeds.bbci.co.uk/news/world/rss.xml", "tier": 1, "weight": 1.0},
    {"source_name": "AFP via Google", "source_type": "rss", "url": "https://news.google.com/rss/search?q=AFP+breaking", "tier": 1, "weight": 1.0},
    {"source_name": "CNN Politics", "source_type": "rss", "url": "http://rss.cnn.com/rss/cnn_allpolitics.rss", "tier": 1, "weight": 0.95},
    {"source_name": "Guardian World", "source_type": "rss", "url": "https://www.theguardian.com/world/rss", "tier": 1, "weight": 0.85},
    # ══════════════════════════════════════════════════════════════════
    # Tier 1 — X/Twitter accounts via RSSHub (agencies)
    # ══════════════════════════════════════════════════════════════════
    {"source_name": "X @Reuters", "source_type": "x_rss", "url": f"{RSSHUB}/Reuters", "tier": 1, "weight": 1.0},
    {"source_name": "X @AP", "source_type": "x_rss", "url": f"{RSSHUB}/AP", "tier": 1, "weight": 1.0},
    {"source_name": "X @AFP", "source_type": "x_rss", "url": f"{RSSHUB}/AFP", "tier": 1, "weight": 1.0},
    {"source_name": "X @BBCBreaking", "source_type": "x_rss", "url": f"{RSSHUB}/BBCBreaking", "tier": 1, "weight": 1.0},
    # ── X — Geopolitics ──────────────────────────────────────────────
    {"source_name": "X @sentdefender", "source_type": "x_rss", "url": f"{RSSHUB}/sentdefender", "tier": 1, "weight": 0.90},
    {"source_name": "X @disclosetv", "source_type": "x_rss", "url": f"{RSSHUB}/disclosetv", "tier": 1, "weight": 0.90},
    {"source_name": "X @spectatorindex", "source_type": "x_rss", "url": f"{RSSHUB}/spectatorindex", "tier": 1, "weight": 0.85},
    {"source_name": "X @IntelCrab", "source_type": "x_rss", "url": f"{RSSHUB}/IntelCrab", "tier": 1, "weight": 0.85},
    # ── X — US Politics ──────────────────────────────────────────────
    {"source_name": "X @politico", "source_type": "x_rss", "url": f"{RSSHUB}/politico", "tier": 1, "weight": 0.90},
    {"source_name": "X @thehill", "source_type": "x_rss", "url": f"{RSSHUB}/thehill", "tier": 1, "weight": 0.90},
    {"source_name": "X @axios", "source_type": "x_rss", "url": f"{RSSHUB}/axios", "tier": 1, "weight": 0.85},
    {"source_name": "X @nytpolitics", "source_type": "x_rss", "url": f"{RSSHUB}/nytpolitics", "tier": 1, "weight": 0.85},
    # ── X — Markets & Macro ──────────────────────────────────────────
    {"source_name": "X @markets", "source_type": "x_rss", "url": f"{RSSHUB}/markets", "tier": 1, "weight": 0.85},
    {"source_name": "X @business", "source_type": "x_rss", "url": f"{RSSHUB}/business", "tier": 1, "weight": 0.85},
    {"source_name": "X @financialtimes", "source_type": "x_rss", "url": f"{RSSHUB}/financialtimes", "tier": 1, "weight": 0.85},
    # ── X — Crypto / Prediction Markets ──────────────────────────────
    {"source_name": "X @Polymarket", "source_type": "x_rss", "url": f"{RSSHUB}/Polymarket", "tier": 1, "weight": 0.80},
    {"source_name": "X @whale_alert", "source_type": "x_rss", "url": f"{RSSHUB}/whale_alert", "tier": 1, "weight": 0.70},
    {"source_name": "X @DeItaone", "source_type": "x_rss", "url": f"{RSSHUB}/DeItaone", "tier": 1, "weight": 0.95},
    # ══════════════════════════════════════════════════════════════════
    # Tier 2 — World News API (< 5 min)
    # ══════════════════════════════════════════════════════════════════
    {"source_name": "World News API", "source_type": "api", "url": "https://api.worldnewsapi.com", "tier": 2, "weight": 0.70},
    # Tier 3 — Specialised (optional, currently empty)
    # NOTE: Metaculus RSS (403) and blog.polymarket.com (DNS dead) were
    # removed 2026-05-06 — both URLs no longer serve content. Kept the
    # category for future re-population.
]


async def seed():
    async with async_session_factory() as session:
        for src in SOURCES:
            exists = await session.execute(
                select(SourceRegistry).where(
                    SourceRegistry.source_name == src["source_name"]
                )
            )
            if exists.scalar_one_or_none():
                continue
            session.add(SourceRegistry(**src))
        await session.commit()
        print(f"Seeded {len(SOURCES)} sources into sources_registry")


if __name__ == "__main__":
    asyncio.run(seed())
