"""Event summarizer — LLM call to create event title + summary from article cluster.

Uses versioned prompt from prompts/event_summary_v1.txt.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "event_summary_v1.txt"


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Prompt file not found at %s, using fallback", PROMPT_PATH)
        return "You are a news summarizer. Summarize multiple articles into one concise event."


class EventSummarizer:
    def __init__(self):
        self.client = get_openai_client()
        self.system_prompt = _load_system_prompt()

    async def summarize(self, articles: list[dict]) -> Optional[dict]:
        """Summarize a cluster of articles into an event title + summary.

        Returns dict with keys: title, summary, key_entities
        """
        if not articles:
            return None

        formatted = []
        for i, a in enumerate(articles[:5], 1):
            title = a.get("title", "")
            text = a.get("clean_text", a.get("content", ""))[:500]
            source = a.get("source_name", "")
            formatted.append(f"[{i}] ({source}) {title}\n{text}")

        user_msg = "\n\n".join(formatted)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_msg},
        ]

        try:
            raw = await self.client.chat_completion(
                messages=messages,
                call_type="event_summary",
                max_tokens=400,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            if raw:
                parsed = json.loads(raw)
                return {
                    "event_title": parsed.get("event_title") or parsed.get("title"),
                    "event_summary": parsed.get("event_summary")
                    or parsed.get("summary"),
                    "key_entities": parsed.get("key_entities"),
                    "event_type": parsed.get("event_type"),
                }
        except json.JSONDecodeError:
            logger.warning("Event summary returned invalid JSON")
        except Exception as e:
            logger.error("Event summarization error: %s", e)

        return None


def create_event_summarizer() -> EventSummarizer:
    return EventSummarizer()
