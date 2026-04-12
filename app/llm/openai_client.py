"""OpenAI client with retry and cost logging."""

import logging
from typing import Optional

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.db.database import async_session_factory
from app.db.models import LLMCostLog

logger = logging.getLogger(__name__)
settings = get_settings()

# Cost per 1M tokens (approximate)
COST_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}


class OpenAIClient:
    """OpenAI client with retry and cost logging."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the client.

        Args:
            api_key: OpenAI API key.
        """
        self._client = AsyncOpenAI(
            api_key=api_key or settings.openai_api_key,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def chat_completion(
        self,
        messages: list[dict],
        model: str = "gpt-4o-mini",
        max_tokens: int = 400,
        temperature: float = 0.7,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        """Create a chat completion.

        Args:
            messages: Chat messages.
            model: Model to use.
            max_tokens: Maximum output tokens.
            temperature: Temperature setting.
            response_format: Response format (e.g., {"type": "json_object"}).

        Returns:
            Response text.
        """
        try:
            params = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }

            if response_format:
                params["response_format"] = response_format

            response = await self._client.chat.completions.create(**params)

            # Log cost
            await self._log_cost(
                model=model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise

    async def _log_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Log API cost.

        Args:
            model: Model used.
            input_tokens: Input token count.
            output_tokens: Output token count.
        """
        costs = COST_PER_1M.get(model, COST_PER_1M["gpt-4o-mini"])

        cost = (
            (input_tokens / 1_000_000) * costs["input"]
            + (output_tokens / 1_000_000) * costs["output"]
        )

        try:
            async with async_session_factory() as session:
                log = LLMCostLog(
                    model=model,
                    tokens_input=input_tokens,
                    tokens_output=output_tokens,
                    cost_eur=cost,
                )
                session.add(log)
                await session.commit()
        except Exception as e:
            logger.error(f"Cost logging error: {e}")


# Global client
_openai_client: Optional[OpenAIClient] = None


def create_openai_client() -> OpenAIClient:
    """Create an OpenAI client.

    Returns:
        Configured OpenAIClient.
    """
    return OpenAIClient()


def get_openai_client() -> OpenAIClient:
    """Get global OpenAI client.

    Returns:
        Global OpenAIClient.
    """
    global _openai_client
    if _openai_client is None:
        _openai_client = create_openai_client()
    return _openai_client