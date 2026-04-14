"""OpenAI client with retry and cost logging."""

import logging
from typing import Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import LLMCostLog

logger = logging.getLogger(__name__)
settings = get_settings()

COST_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def chat_completion(
        self,
        messages: list[dict],
        call_type: str = "unknown",
        model: Optional[str] = None,
        max_tokens: int = 400,
        temperature: float = 0.3,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        model = model or settings.openai_llm_model

        params = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if response_format:
            params["response_format"] = response_format

        response = await self._client.chat.completions.create(**params)

        await self._log_cost(
            call_type=call_type,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        return response.choices[0].message.content

    async def _log_cost(
        self,
        call_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        costs = COST_PER_1M.get(model, COST_PER_1M["gpt-4o-mini"])
        cost_usd = (
            (input_tokens / 1_000_000) * costs["input"]
            + (output_tokens / 1_000_000) * costs["output"]
        )

        try:
            async with get_session_factory()() as session:
                session.add(LLMCostLog(
                    call_type=call_type,
                    model=model,
                    tokens_input=input_tokens,
                    tokens_output=output_tokens,
                    cost_usd=cost_usd,
                ))
                await session.commit()
        except Exception as e:
            logger.warning("Cost logging failed: %s", e)


_openai_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client


def create_openai_client() -> OpenAIClient:
    """Alias for backward compat."""
    return get_openai_client()
