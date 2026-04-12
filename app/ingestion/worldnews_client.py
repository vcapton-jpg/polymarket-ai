"""World News API client for news ingestion."""

import logging
from datetime import datetime
from typing import Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WorldNewsClient:
    """Client for World News API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the World News API client.

        Args:
            api_key: World News API key. Uses setting if not provided.
        """
        self.api_key = api_key or settings.worldnews_api_key
        self.base_url = "https://api.worldnewsapi.com"
        self._session: Optional[httpx.AsyncClient] = None

    async def _get_session(self) -> httpx.AsyncClient:
        """Get or create HTTP session."""
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(
                headers={"X-Api-Key": self.api_key},
                timeout=30.0,
            )
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def fetch_top_news(
        self,
        categories: Optional[list[str]] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Fetch top news from World News API.

        Args:
            categories: List of categories to filter.
            limit: Maximum number of articles.

        Returns:
            List of news articles.
        """
        if not self.api_key:
            logger.warning("WorldNews API key not configured")
            return []

        articles = []

        try:
            session = await self._get_session()

            # Build request parameters
            params = {
                "language": "en",
                "limit": limit,
            }

            if categories:
                params["categories"] = ",".join(categories)

            response = await session.get(
                f"{self.base_url}/top-news",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                articles_raw = data.get("articles", [])

                for article in articles_raw:
                    articles.append(
                        {
                            "url": article.get("url", ""),
                            "title": article.get("title", ""),
                            "content": article.get("text", ""),
                            "source": article.get("source", {}).get("name", ""),
                            "source_tier": 3,
                            "source_weight": 0.5,
                            "published_date": article.get("published_at"),
                            "ingestion_date": datetime.utcnow(),
                            # Approximate lag (World News API aggregates with some delay)
                            "ingestion_lag_seconds": 300,
                        }
                    )

            logger.info(f"Fetched {len(articles)} articles from World News API")

        except Exception as e:
            logger.error(f"Error fetching from World News API: {e}")

        return articles

    async def fetch_latest_news(
        self,
        source_country: str = "us",
        limit: int = 50,
    ) -> list[dict]:
        """Fetch latest news from World News API.

        Args:
            source_country: Source country code.
            limit: Maximum number of articles.

        Returns:
            List of news articles.
        """
        if not self.api_key:
            return []

        articles = []

        try:
            session = await self._get_session()

            params = {
                "source-country": source_country,
                "language": "en",
                "limit": limit,
            }

            response = await session.get(
                f"{self.base_url}/latest-news",
                params=params,
            )

            if response.status_code == 200:
                data = response.json()
                articles_raw = data.get("articles", [])

                for article in articles_raw:
                    articles.append(
                        {
                            "url": article.get("url", ""),
                            "title": article.get("title", ""),
                            "content": article.get("text", ""),
                            "source": article.get("source", {}).get("name", ""),
                            "source_tier": 3,
                            "source_weight": 0.5,
                            "published_date": article.get("published_at"),
                            "ingestion_date": datetime.utcnow(),
                            "ingestion_lag_seconds": 300,
                        }
                    )

        except Exception as e:
            logger.error(f"Error fetching latest news: {e}")

        return articles


def create_worldnews_client() -> WorldNewsClient:
    """Create a World News API client.

    Returns:
        Configured WorldNewsClient instance.
    """
    return WorldNewsClient()