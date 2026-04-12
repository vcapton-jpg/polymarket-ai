"""Impact analyzer using LLM for event-market analysis."""

import json
import logging
from typing import Optional

from app.llm.openai_client import create_openai_client

logger = logging.getLogger(__name__)


# Impact analysis prompt
IMPACT_PROMPT = """Analyze the potential market impact for this prediction market given the event.

Event: {event_text}
Market: {market_question}

Provide a JSON analysis with:
- "summary": Brief summary of the event's relevance
- "impact_score": 0-100 impact on the market
- "direction": "YES" or "NO" (most likely outcome)
- "catalysts": List of factors that could move the market
- "risks": List of risk factors
- "confidence": 0-100 confidence in this analysis
- "time_sensitivity": "high", "medium", or "low"
- "reasoning": Brief explanation

Return ONLY valid JSON."""


class ImpactAnalyzer:
    """Analyzer for market impact using LLM."""

    def __init__(self):
        """Initialize the analyzer."""
        self.client = create_openai_client()

    async def analyze(
        self,
        event_text: str,
        market_question: str,
    ) -> Optional[dict]:
        """Analyze market impact.

        Args:
            event_text: Event text.
            market_question: Market question.

        Returns:
            Analysis dict or None.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a prediction market analyst.",
            },
            {
                "role": "user",
                "content": IMPACT_PROMPT.format(
                    event_text=event_text[:1000],
                    market_question=market_question,
                ),
            },
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
            logger.error(f"Impact analysis error: {e}")

        return None


def create_impact_analyzer() -> ImpactAnalyzer:
    """Create an impact analyzer.

    Returns:
        Configured ImpactAnalyzer.
    """
    return ImpactAnalyzer()