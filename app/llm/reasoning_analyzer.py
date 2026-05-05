"""Per-signal LLM reasoning analyzer — structured output with excerpt validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "signal_reasoning_v1.txt"

MIN_REASONING_CHARS = 100
MAX_REASONING_CHARS = 600


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def compute_tier_mix(articles: list[dict[str, Any]]) -> dict[str, int]:
    mix: dict[str, int] = {}
    for a in articles:
        tier = a.get("source_tier")
        if tier is None:
            continue
        mix[f"tier_{int(tier)}"] = mix.get(f"tier_{int(tier)}", 0) + 1
    return mix


def validate_output(
    out: dict[str, Any], articles: list[dict[str, Any]]
) -> tuple[list[str], dict[str, Any]]:
    """Return (errors, cleaned_output). If errors is non-empty the signal must be rejected."""
    errs: list[str] = []
    reasoning = (out.get("reasoning") or "").strip()
    if len(reasoning) < MIN_REASONING_CHARS:
        errs.append(f"reasoning too short ({len(reasoning)} chars, need >= {MIN_REASONING_CHARS})")

    source_names = {a["source_name"] for a in articles}
    if not any(sn in reasoning for sn in source_names):
        errs.append("reasoning does not cite any input source name")

    text_by_id = {a["news_clean_id"]: a["clean_text"] for a in articles}
    cleaned_excerpts: list[dict[str, Any]] = []
    for e in out.get("article_excerpts") or []:
        nid = e.get("news_clean_id")
        exc = (e.get("excerpt") or "").strip()
        if nid in text_by_id and exc and exc in text_by_id[nid]:
            cleaned_excerpts.append(
                {"news_clean_id": nid, "excerpt": exc, "relevance": float(e.get("relevance", 0.0))}
            )

    if not cleaned_excerpts:
        errs.append("zero valid excerpt substrings")

    cleaned = dict(out)
    cleaned["article_excerpts"] = cleaned_excerpts
    cleaned["source_tier_mix"] = compute_tier_mix(articles)
    return errs, cleaned


class ReasoningAnalyzer:
    def __init__(self) -> None:
        self.client = get_openai_client()
        self.system_prompt = _load_prompt()
        self._model = getattr(
            get_settings(), "openai_reasoning_model", "gpt-4o-mini-2024-07-18"
        )

    @property
    def model_version(self) -> str:
        return self._model

    async def analyze(
        self,
        *,
        event_title: str,
        event_summary: str,
        articles: list[dict[str, Any]],
        market_question: str,
        market_price: float,
        market_direction_hint: str | None = None,
    ) -> dict[str, Any] | None:
        articles_for_prompt = [
            {
                "news_clean_id": a["news_clean_id"],
                "title": a["title"],
                "source_name": a["source_name"],
                "source_tier": a.get("source_tier"),
                "publish_date": a.get("publish_date"),
                "clean_text": a["clean_text"][:800],
            }
            for a in articles[:5]
        ]
        user_msg = json.dumps(
            {
                "event": {"title": event_title, "summary": event_summary},
                "market": {
                    "question": market_question,
                    "price": market_price,
                    "direction_hint": market_direction_hint,
                },
                "articles": articles_for_prompt,
            },
            ensure_ascii=False,
        )

        try:
            raw = await self.client.chat_completion(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                call_type="signal_reasoning",
                model=self._model,
                max_tokens=700,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            logger.warning("ReasoningAnalyzer: LLM call failed: %s", e)
            raise

        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("ReasoningAnalyzer: invalid JSON from LLM: %r", raw[:200])
            return None

        errs, cleaned = validate_output(parsed, articles_for_prompt)
        if errs:
            logger.info("ReasoningAnalyzer rejected: %s", errs)
            return None
        return cleaned


def create_reasoning_analyzer() -> ReasoningAnalyzer:
    """Backward-compat alias. New call sites should use `get_reasoning_analyzer()`."""
    return get_reasoning_analyzer()


# Module-level singleton — see `app.llm.event_summarizer.get_event_summarizer`
# for the rationale (H9 audit follow-up 2026-05-05). Same shape: wrapper
# allocated once, prompt file read once, underlying OpenAIClient already
# singleton.
_reasoning_analyzer_singleton: Optional["ReasoningAnalyzer"] = None


def get_reasoning_analyzer() -> "ReasoningAnalyzer":
    """Return the process-wide `ReasoningAnalyzer` singleton."""
    global _reasoning_analyzer_singleton
    if _reasoning_analyzer_singleton is None:
        _reasoning_analyzer_singleton = ReasoningAnalyzer()
    return _reasoning_analyzer_singleton
