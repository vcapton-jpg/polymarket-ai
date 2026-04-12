"""RSS scraper for news ingestion."""

import logging
from datetime import datetime
from typing import Optional

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.ingestion.sources_registry import get_source_weight

logger = logging.getLogger(__name__)
settings = get_settings()

# Default RSS feeds configuration
DEFAULT_RSS_FEEDS = [
    {"name": "Reuters", "url": "https://www.reutersagency.com/feed/", "tier": 1},
    {"name": "AP", "url": "https://feeds.ap.org/news/rss", "tier": 1},
    {"name": "AFP", "url": "https://www.afp.com/rss", "tier": 1},
    {"name": "BBC", "url": "http://feeds.bbci.co.uk/news/world/rss.xml", "tier": 1},
    {"name": "Guardian", "url": "https://www.theguardian.com/world/rss", "tier": 1},
]


class RSSScraper:
    """Scraper for RSS feeds."""

    def __init__(self, feeds: Optional[list[dict]] = None):
        """Initialize the RSS scraper.

        Args:
            feeds: List of feed configurations. Uses defaults if not provided.
        """
        self.feeds = feeds or DEFAULT_RSS_FEEDS

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def fetch_feed(self, url: str) -> list[dict]:
        """Fetch and parse an RSS feed.

        Args:
            url: URL of the RSS feed.

        Returns:
            List of parsed articles.

        Raises:
            Exception: If the feed cannot be fetched.
        """
        try:
            feed = feedparser.parse(url)
            articles = []

            for entry in feed.entries:
                # Parse publication date
                published_date = None
                if hasattr(entry, "published"):
                    try:
                        published_date = date_parser.parse(entry.published)
                    except Exception:
                        pass

                # Extract content
                content = ""
                if hasattr(entry, "summary"):
                    content = entry.summary
                elif hasattr(entry, "description"):
                    content = entry.description

                # Strip HTML from content
                if content:
                    soup = BeautifulSoup(content, "lxml")
                    content = soup.get_text(strip=True)

                article = {
                    "url": entry.get("link", ""),
                    "title": entry.get("title", ""),
                    "content": content,
                    "published_date": published_date,
                }

                if article["url"] and article["title"]:
                    articles.append(article)

            logger.info(f"Fetched {len(articles)} articles from {url}")
            return articles

        except Exception as e:
            logger.error(f"Error fetching feed {url}: {e}")
            raise

    def fetch_all(self) -> list[dict]:
        """Fetch all configured RSS feeds.

        Returns:
            List of all articles from all feeds.
        """
        all_articles = []

        for feed_config in self.feeds:
            try:
                articles = self.fetch_feed(feed_config["url"])
                for article in articles:
                    article["source"] = feed_config["name"]
                    article["source_tier"] = feed_config["tier"]
                    source_info = get_source_weight(feed_config["name"])
                    article["source_weight"] = source_info["weight"] if source_info else 1.0
                    article["ingestion_date"] = datetime.utcnow()

                    # Calculate ingestion lag
                    if article.get("published_date"):
                        lag = (
                            article["ingestion_date"] - article["published_date"]
                        ).total_seconds()
                        article["ingestion_lag_seconds"] = lag

                all_articles.extend(articles)
            except Exception as e:
                logger.error(f"Error fetching feed {feed_config['name']}: {e}")
                continue

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles


def create_rss_scraper() -> RSSScraper:
    """Create an RSS scraper with default feeds.

    Returns:
        Configured RSSScraper instance.
    """
    return RSSScraper()