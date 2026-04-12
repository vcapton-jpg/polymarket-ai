"""Event summarizer using LLM."""

import json
import logging
from typing import Optional

from app.llm.openai_client import create_openai_client
from app.db.models import Event

logger = logging.getLogger(__name__)


# Summarization prompt
SUMMARIZE_PROMPT = """You are a news summarizer. Given multiple news articles about the same event, create a concise summary.

Articles:
{articles}

Create a JSON summary with:
- "title": A short title for the event
- "summary": A 2-3 sentence summary of what happened
- "key_entities": Key people, places, and organizations involved

Return ONLY valid JSON."""


class EventSummarizer:
    """Summarizer for events using LLM."""

    def __init__(self):
        """Initialize the summarizer."""
        self.client = create_openai_client()

    async def summarize_multi_source(
        self,
        articles: list[dict],
    ) -> Optional[dict]:
        """Summarize multi-source event.

        Args:
            articles: List of article dictionaries.

        Returns:
            Summary dict or None.
        """
        if len(articles) < 2:
            return None

        # Format articles
        articles_text = []
        for i, article in enumerate(articles[:5], 1):
            articles_text.append(
                f"{i}. {article.get('title', '')}\n{article.get('content', '')[:500]}"
            )

        articles_str = "\n\n".join(articles_text)

        messages = [
            {"role": "system", "content": "You are a news summarizer."},
            {"role": "user", "content": SUMMARIZE_PROMPT.format(articles=articles_str)},
        ]

        try:
            response = await self.client.chat_completion(
                messages=messages,
                model="gpt-4o-mini",
                max_tokens=400,
                response_format={"type": "json_object"},
            )

            if response:
                return json.loads(response)

        except Exception as e:
            logger.error(f"Summarization error: {e}")

        return None

    def summarize_single_source(self, article: dict) -> str:
        """Summarize single-source event (no LLM).

        Args:
            article: Article dictionary.

        Returns:
            Summary text.
        """
        title = article.get("title", "")
        content = article.get("content", "")

        # Use title + first 400 chars of content
        return f"{title} {content[:400]}"


def create_event_summarizer() -> EventSummarizer:
    """Create an event summarizer.

    Returns:
        Configured EventSummarizer.
    """
    return EventSummarizer()