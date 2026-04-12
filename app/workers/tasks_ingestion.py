"""Celery tasks for ingestion pipeline."""

import logging
from datetime import datetime

from app.workers.celery_app import celery_app
from app.db.database import async_session_factory
from app.db.models import News, ArticleEntity
from app.ingestion.rss_scraper import create_rss_scraper
from app.processing.news_cleaner import create_news_cleaner
from app.processing.embedding_service import get_embedding
from app.processing.ner_extractor import create_ner_extractor

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def ingest_rss_feeds(self):
    """Ingest news from RSS feeds."""
    scraper = create_rss_scraper()
    articles = scraper.fetch_all()

    if not articles:
        return {"status": "no_articles", "count": 0}

    cleaner = create_news_cleaner()
    ner = create_ner_extractor()

    async def save_articles():
        async with async_session_factory() as session:
            saved_count = 0

            for article in articles:
                # Clean article
                cleaned = cleaner.clean_article(article)

                # Check quality
                if not cleaner.should_ingest(cleaned):
                    continue

                # Get embedding
                embedding = None
                text = f"{cleaned['title']} {cleaned['content'][:500]}"
                embedding = get_embedding(text)

                # Extract entities
                entities = ner.extract_entities(cleaned.get("content", ""))

                # Save news
                news = News(
                    url=cleaned.get("url"),
                    title=cleaned.get("title"),
                    content=cleaned.get("content"),
                    source=cleaned.get("source"),
                    source_tier=cleaned.get("source_tier", 2),
                    source_weight=cleaned.get("source_weight", 0.5),
                    language=cleaned.get("language"),
                    published_date=cleaned.get("published_date"),
                    ingestion_date=datetime.utcnow(),
                    ingestion_lag_seconds=cleaned.get("ingestion_lag_seconds"),
                    word_count=cleaned.get("word_count"),
                    embedding_computed=embedding is not None,
                )
                session.add(news)
                await session.flush()

                # Save entities
                for entity in entities:
                    article_entity = ArticleEntity(
                        news_id=news.id,
                        entity_type=entity.get("entity_type"),
                        entity_value=entity.get("entity_value"),
                    )
                    session.add(article_entity)

                saved_count += 1

            await session.commit()
            return {"status": "saved", "count": saved_count}

    return {"status": "scheduled", "count": len(articles)}


@celery_app.task(bind=True, max_retries=3)
def cleanup_duplicates(self):
    """Clean up duplicate articles."""
    # SimHash-based deduplication would be implemented here
    logger.info("Running duplicate cleanup")
    return {"status": "completed"}