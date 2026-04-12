"""News cleaner for text processing."""

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

# Language codes to accept
ACCEPTED_LANGUAGES = {"en"}

# Minimum word count for quality
MIN_WORD_COUNT = 50


class NewsCleaner:
    """Cleaner for news articles."""

    def clean_html(self, text: str) -> str:
        """Strip HTML tags and clean text.

        Args:
            text: Text containing HTML.

        Returns:
            Cleaned text.
        """
        if not text:
            return ""

        soup = BeautifulSoup(text, "lxml")
        cleaned = soup.get_text(separator=" ")

        return self.normalize_whitespace(cleaned)

    def normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text.

        Args:
            text: Input text.

        Returns:
            Text with normalized whitespace.
        """
        # Replace multiple whitespace with single space
        text = re.sub(r"\s+", " ", text)

        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def detect_language(self, text: str) -> Optional[str]:
        """Detect language of text.

        Args:
            text: Text to detect.

        Returns:
            Language code or None.
        """
        if not text or len(text) < 20:
            return None

        try:
            lang = detect(text)
            return lang
        except LangDetectException:
            logger.debug("Could not detect language")
            return None

    def is_english(self, text: str) -> bool:
        """Check if text is in English.

        Args:
            text: Text to check.

        Returns:
            True if text is in English.
        """
        lang = self.detect_language(text)
        return lang in ACCEPTED_LANGUAGES if lang else False

    def count_words(self, text: str) -> int:
        """Count words in text.

        Args:
            text: Input text.

        Returns:
            Word count.
        """
        words = text.split()
        return len(words)

    def clean_article(self, article: dict) -> dict:
        """Clean a complete article.

        Args:
            article: Raw article data.

        Returns:
            Cleaned article data.
        """
        cleaned = article.copy()

        # Clean title
        if cleaned.get("title"):
            cleaned["title"] = self.normalize_whitespace(
                self.clean_html(cleaned["title"])
            )

        # Clean content
        if cleaned.get("content"):
            cleaned["content"] = self.clean_html(cleaned["content"])
            cleaned["content"] = self.normalize_whitespace(cleaned["content"])

        # Detect language
        text_for_lang = cleaned.get("title", "") + " " + cleaned.get("content", "")
        cleaned["language"] = self.detect_language(text_for_lang)

        # Count words
        cleaned["word_count"] = self.count_words(cleaned.get("content", ""))

        # Check quality
        cleaned["is_duplicate"] = False
        cleaned["quality_passed"] = (
            cleaned.get("language") == "en"
            and cleaned.get("word_count", 0) >= MIN_WORD_COUNT
        )

        return cleaned

    def should_ingest(self, article: dict) -> bool:
        """Check if article should be ingested.

        Args:
            article: Cleaned article data.

        Returns:
            True if article passes quality filters.
        """
        return article.get("quality_passed", False)


def create_news_cleaner() -> NewsCleaner:
    """Create a news cleaner instance.

    Returns:
        Configured NewsCleaner.
    """
    return NewsCleaner()