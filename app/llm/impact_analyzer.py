"""Impact analyzer — LLM call to assess event → market impact.

Uses versioned prompt from prompts/impact_analysis_v1.txt.
Default model: gpt-4o-mini (configurable via OPENAI_IMPACT_MODEL).
Pre-2026-04-28 the default was gpt-4o which represented 97 % of the
LLM bill (~$27/month over 7 681 calls). The impact-analysis prompt is
highly structured and gpt-4o-mini matches gpt-4o in side-by-side
quality spot-checks for this specific call shape, so the default was
down-tiered. Operators that want gpt-4o back can set
`OPENAI_IMPACT_MODEL=gpt-4o` in their environment.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "prompts" / "impact_analysis_v1.txt"


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning("Prompt file not found at %s, using fallback", PROMPT_PATH)
        return "You are a prediction market analyst. Analyze event impact on the given market."


class ImpactAnalyzer:
    def __init__(self):
        self.client = get_openai_client()
        self.system_prompt = _load_system_prompt()
        self._model = get_settings().openai_impact_model

    async def analyze(
        self,
        event_text: str,
        market_question: str,
    ) -> Optional[dict]:
        """Analyze event → market impact using LLM.

        Returns parsed JSON dict or None on failure.
        """
        user_msg = (
            f"Event: {event_text[:1500]}\n\n"
            f"Market question: {market_question}"
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_msg},
        ]

        try:
            raw = await self.client.chat_completion(
                messages=messages,
                call_type="impact_analysis",
                model=self._model,
                max_tokens=500,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
            if raw:
                return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Impact analysis returned invalid JSON")
        except Exception as e:
            logger.error("Impact analysis error: %s", e)

        return None


def create_impact_analyzer() -> ImpactAnalyzer:
    """Backward-compat alias. New call sites should use `get_impact_analyzer()`."""
    return get_impact_analyzer()


# Module-level singleton — see `app.llm.event_summarizer.get_event_summarizer`
# for the rationale (H9 audit follow-up 2026-05-05). Same shape: wrapper
# allocated once, prompt file read once, underlying OpenAIClient already
# singleton.
_impact_analyzer_singleton: Optional["ImpactAnalyzer"] = None


def get_impact_analyzer() -> "ImpactAnalyzer":
    """Return the process-wide `ImpactAnalyzer` singleton."""
    global _impact_analyzer_singleton
    if _impact_analyzer_singleton is None:
        _impact_analyzer_singleton = ImpactAnalyzer()
    return _impact_analyzer_singleton
