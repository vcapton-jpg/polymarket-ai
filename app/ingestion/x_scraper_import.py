"""Parse exports from 𝕏-scraper (Firefox extension).

See: https://fmoncomble.github.io/X-scraper/
Typical JSON: list of objects with tweet text, created_at, screen_name, url.
"""

from __future__ import annotations

import csv
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

logger = logging.getLogger(__name__)


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=UTC)
    try:
        dt = date_parser.parse(str(val))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except (ValueError, TypeError):
        return None


def _tweet_text(obj: dict) -> str:
    return (
        (obj.get("full_text") or obj.get("text") or obj.get("tweet") or "")
        .strip()
    )


def _tweet_url(obj: dict) -> str | None:
    u = obj.get("url") or obj.get("tweet_url") or obj.get("link") or obj.get("permalink")
    if u:
        return str(u).strip() or None
    return None


def _screen_name(obj: dict) -> str:
    if isinstance(obj.get("user"), dict):
        sn = obj["user"].get("screen_name") or obj["user"].get("username")
        if sn:
            return str(sn)
    sn = obj.get("screen_name") or obj.get("username") or obj.get("author")
    return str(sn).strip() if sn else "unknown"


def _iter_records(data: Any) -> Iterator[dict]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return
    if isinstance(data, dict):
        for key in ("tweets", "data", "statuses", "items"):
            if key in data and isinstance(data[key], list):
                for item in data[key]:
                    if isinstance(item, dict):
                        yield item
                return
        yield data


def records_from_json(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    data = json.loads(raw)
    return list(_iter_records(data))


def records_from_csv(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def normalize_x_scraper_row(obj: dict, *, source_label: str = "x_scraper") -> dict | None:
    """Return a dict suitable for News insertion: url, title, text, publish_date, source fields."""
    text = _tweet_text(obj)
    if len(text) < 3:
        return None

    url = _tweet_url(obj)
    if not url:
        h = abs(hash(text)) % (10**12)
        url = f"https://x-scraper.local/t/{h}"

    author = _screen_name(obj)
    title = text if len(text) <= 280 else (text[:277] + "…")
    pub = _parse_dt(
        obj.get("created_at")
        or obj.get("date")
        or obj.get("timestamp")
    )

    return {
        "url": url[:1020],
        "title": title[:1024],
        "text": text,
        "source_name": f"{source_label}:{author}"[:255],
        "source_tier": 2,
        "source_weight": 0.55,
        "publish_date": pub,
        "ingestion_lag_seconds": None,
    }


def normalize_csv_row(row: dict, *, source_label: str = "x_scraper") -> dict | None:
    """Map CSV column names from 𝕏-scraper exports (flexible headers)."""
    lower = {k.lower().strip(): v for k, v in row.items() if k}
    text = (
        lower.get("full_text")
        or lower.get("text")
        or lower.get("tweet")
        or lower.get("content")
        or ""
    )
    if isinstance(text, str):
        text = text.strip()
    else:
        text = str(text).strip()
    obj = {
        "full_text": text,
        "url": lower.get("url") or lower.get("tweet_url") or lower.get("link"),
        "created_at": lower.get("created_at") or lower.get("date") or lower.get("timestamp"),
        "screen_name": lower.get("screen_name") or lower.get("author") or lower.get("username"),
    }
    return normalize_x_scraper_row(obj, source_label=source_label)


def load_articles_from_file(path: Path) -> list[dict]:
    """Load normalized article dicts from a JSON or CSV file."""
    path = Path(path)
    suf = path.suffix.lower()
    out: list[dict] = []

    if suf == ".json":
        for rec in records_from_json(path):
            n = normalize_x_scraper_row(rec)
            if n:
                out.append(n)
    elif suf == ".csv":
        for rec in records_from_csv(path):
            n = normalize_csv_row(rec)
            if n:
                out.append(n)
    else:
        logger.warning("Unsupported X-scraper file type: %s", path)

    return out
