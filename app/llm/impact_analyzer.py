"""Impact analyzer — LLM call to assess event → market impact.

Uses versioned prompt from prompts/impact_analysis_v1.txt.
Uses gpt-4o (configurable via OPENAI_IMPACT_MODEL) for higher quality.
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
    return ImpactAnalyzer()
