"""OpenAI client with retry, cost logging, and a 24 h budget circuit breaker.

The breaker reads `settings.llm_cost_alert_usd` (defined in `app/core/config.py`,
default 30 USD). Before every chat completion we check the cumulative cost
of LLM calls in the last 24 h; if it has crossed the threshold we raise
`LLMBudgetExceeded` and refuse the call. The tenacity `@retry` decorator
is configured to **not** retry on this exception so a single tripped
breaker does not amplify into 3× the cost.

State machine
─────────────
* The 24 h total is cached in process memory with a 60 s TTL — a live
  query on `llm_cost_log` for every prompt would be wasteful.
* After each successful call we tack the just-logged cost onto the cached
  total so a burst inside the same TTL window is still accurately gated.
* Once the breaker is tripped, it self-heals on the next 60 s refresh
  when older `llm_cost_log` rows roll out of the 24 h window.
* `llm_cost_alert_usd <= 0` disables the breaker entirely (escape hatch
  for tests / dev seeding).

This module is the only writer to `llm_cost_log`; spreading the breaker
elsewhere would defeat the cache so anything that needs raw OpenAI access
should go through `OpenAIClient.chat_completion`.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from openai import AsyncOpenAI
from sqlalchemy import func as sa_func
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_not_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import LLMCostLog

logger = logging.getLogger(__name__)
settings = get_settings()

COST_PER_1M = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
}


class LLMBudgetExceeded(RuntimeError):
    """24 h cumulative LLM spend has crossed `llm_cost_alert_usd`.

    Raised by `OpenAIClient.chat_completion` *before* the OpenAI request
    fires, so no further dollars are spent until the rolling window
    drains below the threshold. The retry decorator excludes this type
    so tenacity will not amplify a single trip into multiple charges.
    """


# Module-level cost cache. Mutated under `_COST_LOCK` because asyncio
# tasks can race the refresh-vs-increment paths.
_COST_LOCK = asyncio.Lock()
_COST_STATE: dict[str, float] = {
    "total_usd_24h": 0.0,
    "fetched_at_monotonic": 0.0,
}
_COST_REFRESH_INTERVAL_SEC = 60.0


def _compute_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = COST_PER_1M.get(model, COST_PER_1M["gpt-4o-mini"])
    return (
        (input_tokens / 1_000_000) * costs["input"]
        + (output_tokens / 1_000_000) * costs["output"]
    )


async def _fetch_24h_cost_from_db() -> float:
    """Sum of `llm_cost_log.cost_usd` over the last 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    async with get_session_factory()() as session:
        result = await session.execute(
            select(sa_func.coalesce(sa_func.sum(LLMCostLog.cost_usd), 0)).where(
                LLMCostLog.called_at >= cutoff
            )
        )
        return float(result.scalar() or 0.0)


async def _ensure_under_budget() -> None:
    """Refresh the cache (if stale) and trip the breaker when over budget."""
    threshold = settings.llm_cost_alert_usd
    if threshold <= 0:
        return  # Breaker disabled.

    now = time.monotonic()
    async with _COST_LOCK:
        last_fetch = _COST_STATE["fetched_at_monotonic"]
        is_stale = (now - last_fetch) >= _COST_REFRESH_INTERVAL_SEC
        if is_stale:
            try:
                _COST_STATE["total_usd_24h"] = await _fetch_24h_cost_from_db()
            except Exception:
                # DB hiccup: fall back to whatever the in-memory tally says
                # rather than hard-fail every LLM call. We log loud so an
                # operator sees the breaker is now flying blind.
                logger.warning(
                    "LLM budget check: DB read failed, using cached total %.4f USD",
                    _COST_STATE["total_usd_24h"],
                    exc_info=True,
                )
            _COST_STATE["fetched_at_monotonic"] = now
        total = _COST_STATE["total_usd_24h"]

    if total >= threshold:
        logger.error(
            "LLM cost circuit-breaker tripped: 24h spend $%.2f >= alert threshold $%.2f. "
            "Refusing new chat completions until older calls roll out of the window.",
            total,
            threshold,
        )
        raise LLMBudgetExceeded(
            f"24h LLM cost ${total:.2f} >= alert threshold ${threshold:.2f}"
        )


async def _record_call_cost(cost_usd: float) -> None:
    """Tack the just-logged cost onto the cached 24 h total."""
    async with _COST_LOCK:
        _COST_STATE["total_usd_24h"] += cost_usd


def _reset_cost_state_for_tests() -> None:
    """Test-only — drop the cached total so each test starts clean."""
    _COST_STATE["total_usd_24h"] = 0.0
    _COST_STATE["fetched_at_monotonic"] = 0.0


class OpenAIClient:
    def __init__(self, api_key: Optional[str] = None):
        self._client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=2, max=10),
        # Hard-stop on a tripped breaker — retrying would just keep
        # checking the same cached total and waste 3× the latency.
        retry=retry_if_not_exception_type(LLMBudgetExceeded),
    )
    async def chat_completion(
        self,
        messages: list[dict],
        call_type: str = "unknown",
        model: Optional[str] = None,
        max_tokens: int = 400,
        temperature: float = 0.3,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        await _ensure_under_budget()

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

        cost_usd = await self._log_cost(
            call_type=call_type,
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )
        if cost_usd is not None:
            await _record_call_cost(cost_usd)

        return response.choices[0].message.content

    async def _log_cost(
        self,
        call_type: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> Optional[float]:
        cost_usd = _compute_cost_usd(model, input_tokens, output_tokens)

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
            return None
        return cost_usd


_openai_client: Optional[OpenAIClient] = None


def get_openai_client() -> OpenAIClient:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAIClient()
    return _openai_client


def create_openai_client() -> OpenAIClient:
    """Alias for backward compat."""
    return get_openai_client()
