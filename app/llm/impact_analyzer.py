"""Impact analyzer — LLM call to assess event → market impact.

Prompt version is selected at startup via `settings.impact_prompt_version`
(default `v1`). The version label is suffixed onto the persisted
`llm_model_version` (T-011) so `/admin/stats/extended`'s
`by_llm_model_version` section can split RTP across prompt versions on
prod traffic — that's the measurement loop the plan calls for in §6.

  v1: legacy free-form prompt. Does NOT see the market price.
  v2: price-conditional reasoning — receives `market_yes_price` and
      is required to compare its own `implied_yes_probability` to the
      market before recommending a direction. T-009.

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

_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def _load_system_prompt(version: str) -> str:
    """Load `prompts/impact_analysis_<version>.txt`.

    Falls back to v1 (and emits a warning) if the requested version
    file is missing — operator typo in IMPACT_PROMPT_VERSION shouldn't
    crash the worker on boot.
    """
    path = _PROMPTS_DIR / f"impact_analysis_{version}.txt"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning(
            "impact_analysis prompt version=%r not found at %s, "
            "falling back to v1",
            version, path,
        )
        fallback = _PROMPTS_DIR / "impact_analysis_v1.txt"
        try:
            return fallback.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "You are a prediction market analyst. Analyze event impact on the given market."


class ImpactAnalyzer:
    def __init__(self):
        settings = get_settings()
        self.client = get_openai_client()
        self.prompt_version = settings.impact_prompt_version
        self.system_prompt = _load_system_prompt(self.prompt_version)
        # `_model` flows through `_build_llm_data` to `signals.llm_model_version`.
        # Suffix the prompt version so the admin stats can split RTP by
        # the (model, prompt_version) tuple via a single GROUP BY.
        # Example: "gpt-4o-mini@v1", "gpt-4o-mini@v2".
        self._model = f"{settings.openai_impact_model}@{self.prompt_version}"
        # Keep the bare model name for the actual API call — OpenAI
        # doesn't understand our `@v2` suffix.
        self._raw_model = settings.openai_impact_model

    async def analyze(
        self,
        event_text: str,
        market_question: str,
        market_yes_price: float | None = None,
    ) -> dict | None:
        """Analyze event → market impact using LLM.

        `market_yes_price` is required by v2 (price-conditional prompt)
        and ignored by v1. Caller should always pass it when available —
        v1 silently drops it, v2 silently substitutes 0.50 (neutral
        prior) when it's missing.

        Returns parsed JSON dict or None on failure.
        """
        if self.prompt_version == "v2":
            # v2 wants the price explicitly so it can reason about edge
            # vs the market. Missing price → fall back to a neutral
            # prior of 0.50 so the prompt still has a number to anchor
            # on, but log so a future operator notices that the upstream
            # `_analyze_one` didn't pass one.
            price = market_yes_price if market_yes_price is not None else 0.50
            if market_yes_price is None:
                logger.info(
                    "impact_analysis.v2 missing market_yes_price, using 0.50 prior"
                )
            user_msg = (
                f"Event: {event_text[:1500]}\n\n"
                f"Market question: {market_question}\n"
                f"Market YES price: {price:.4f}"
            )
        else:
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
                model=self._raw_model,
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
