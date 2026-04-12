"""X (Twitter) scraper for news ingestion."""

import logging
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Default X accounts to monitor
DEFAULT_X_ACCOUNTS = [
    {"handle": "Reuters", "tier": 1},
    {"handle": "AP", "tier": 1},
    {"handle": "AFP", "tier": 1},
    {"handle": "BBCNews", "tier": 1},
    {"handle": "skynews", "tier": 1},
    {"handle": "CNBC", "tier": 2},
    {"handle": "business", "tier": 2},
    {"handle": "FT", "tier": 1},
    {"handle": "washingtonpost", "tier": 1},
    {"handle": "nytimes", "tier": 1},
]


class XScraper:
    """Scraper for X (Twitter) accounts."""

    def __init__(self, accounts: Optional[list[dict]] = None):
        """Initialize the X scraper.

        Args:
            accounts: List of account configurations. Uses defaults if not provided.
        """
        self.accounts = accounts or DEFAULT_X_ACCOUNTS

    async def fetch_account_tweets(
        self,
        handle: str,
        max_tweets: int = 10,
    ) -> list[dict]:
        """Fetch recent tweets from an X account.

        Args:
            handle: X account handle.
            max_tweets: Maximum number of tweets to fetch.

        Returns:
            List of tweet data.
        """
        # Note: This requires browser automation
        # In production, use Twitter API or a dedicated scraper service
        tweets = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Navigate to the account's timeline
                await page.goto(f"https://x.com/{handle}", wait_until="networkidle")

                # Wait for tweets to load
                await page.wait_for_selector("[data-testid='tweet']", timeout=10000)

                # Get tweets
                tweet_elements = await page.query_selector_all("[data-testid='tweet']")

                for tweet_elem in tweet_elements[:max_tweets]:
                    try:
                        # Extract tweet text
                        text_elem = await tweet_elem.query_selector(
                            "[data-testid='tweetText']"
                        )
                        text = await text_elem.inner_text() if text_elem else ""

                        # Extract timestamp
                        time_elem = await tweet_elem.query_selector("time")
                        timestamp_str = (
                            await time_elem.get_attribute("datetime")
                            if time_elem
                            else None
                        )

                        # Parse timestamp
                        if timestamp_str:
                            dt = datetime.fromisoformat(
                                timestamp_str.replace("Z", "+00:00")
                            )
                        else:
                            dt = datetime.utcnow()

                        tweets.append(
                            {
                                "url": f"https://x.com/{handle}",
                                "title": text[:200],  # Use first 200 chars as title
                                "content": text,
                                "published_date": dt,
                                "source": handle,
                            }
                        )
                    except Exception as e:
                        logger.debug(f"Error parsing tweet: {e}")
                        continue

                await browser.close()

        except Exception as e:
            logger.error(f"Error fetching tweets from {handle}: {e}")

        return tweets

    async def fetch_all(self) -> list[dict]:
        """Fetch tweets from all configured accounts.

        Returns:
            List of all tweets from all accounts.
        """
        all_tweets = []

        for account in self.accounts:
            try:
                tweets = await self.fetch_account_tweets(
                    account["handle"],
                    max_tweets=10,
                )

                for tweet in tweets:
                    tweet["source_tier"] = account["tier"]
                    # Default weight: tier 1 = 1.0, tier 2 = 0.7, tier 3 = 0.5
                    tweet["source_weight"] = (
                        1.0 if account["tier"] == 1 else 0.7 if account["tier"] == 2 else 0.5
                    )
                    tweet["ingestion_date"] = datetime.utcnow()

                    # Calculate ingestion lag (approximate based on tweet time)
                    if tweet.get("published_date"):
                        lag = (
                            tweet["ingestion_date"] - tweet["published_date"]
                        ).total_seconds()
                        tweet["ingestion_lag_seconds"] = lag

                all_tweets.extend(tweets)
            except Exception as e:
                logger.error(f"Error fetching account {account['handle']}: {e}")
                continue

        logger.info(f"Total tweets fetched: {len(all_tweets)}")
        return all_tweets


def create_x_scraper() -> XScraper:
    """Create an X scraper with default accounts.

    Returns:
        Configured XScraper instance.
    """
    return XScraper()