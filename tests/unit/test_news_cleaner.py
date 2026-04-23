"""Unit tests for news cleaner."""

import pytest
from app.processing.news_cleaner import NewsCleaner


def test_clean_html():
    """Test HTML cleaning."""
    cleaner = NewsCleaner()
    
    text = "<p>Hello World</p>"
    result = cleaner.clean_html(text)
    
    assert "Hello World" in result
    assert "<" not in result


def test_normalize_whitespace():
    """Test whitespace normalization."""
    cleaner = NewsCleaner()
    
    text = "  Hello   World  "
    result = cleaner.normalize_whitespace(text)
    
    assert result == "Hello World"


def test_detect_language_english():
    """Test English language detection."""
    cleaner = NewsCleaner()
    
    text = "This is a test article in English with some normal words."
    result = cleaner.detect_language(text)
    
    assert result == "en"


def test_is_english():
    """Test English check."""
    cleaner = NewsCleaner()
    
    assert cleaner.is_english("This is English text.")
    assert not cleaner.is_english("Este es español.")


def test_count_words():
    """Test word counting."""
    cleaner = NewsCleaner()
    
    text = "Hello World Test"
    count = cleaner.count_words(text)
    
    assert count == 3


def test_clean_article():
    """Test full article cleaning."""
    cleaner = NewsCleaner()
    
    article = {
        "title": "  <h1>Test Title</h1>  ",
        "content": "<p>Content with words.</p>",
    }
    
    result = cleaner.clean_article(article)
    
    assert "title" in result
    assert result["language"] == "en"
    assert result["word_count"] >= 3


def test_should_ingest():
    """Test quality check."""
    cleaner = NewsCleaner()
    
    article_pass = {
        "title": "Test",
        "content": "Word " * 50,
        "language": "en",
        "word_count": 50,
        "quality_passed": True,
    }

    assert cleaner.should_ingest(article_pass)

    article_fail = {
        "title": "Test",
        "content": "Short",
        "language": "en",
        "word_count": 1,
        "quality_passed": False,
    }

    assert not cleaner.should_ingest(article_fail)