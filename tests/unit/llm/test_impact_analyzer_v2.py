"""Pin the prompt-version + price-injection contract of ImpactAnalyzer.

T-009 in docs/PLAN_30D_SIGNAL_QUALITY.md. Three things must hold:

  1. With `impact_prompt_version="v1"`: the system prompt is loaded
     from `prompts/impact_analysis_v1.txt`, the user message does NOT
     contain a "Market YES price:" line, and `_model` is suffixed
     "@v1" so admin stats can split.
  2. With `impact_prompt_version="v2"`: the v2 prompt is loaded, the
     user message DOES contain "Market YES price: <X>", and `_model`
     is suffixed "@v2".
  3. v2 with a missing price falls back to 0.50 + logs (no crash).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import get_settings
from app.llm.impact_analyzer import ImpactAnalyzer
from app.llm.openai_client import _reset_cost_state_for_tests


@pytest.fixture(autouse=True)
def _reset_cost_state():
    """Reset the OpenAIClient module-level cost cache before AND after
    every test in this module. Without this, mocking `chat_completion`
    on the singleton OpenAIClient leaves a populated `_COST_STATE`
    (TTL ~5 min) that breaks the next test file's breaker assertions
    — `tests/unit/llm/test_openai_client_budget.py` was hit on CI
    because pytest runs files in alphabetical order and our test runs
    before it. Cf. PR #104 CI run 25700355529."""
    _reset_cost_state_for_tests()
    yield
    _reset_cost_state_for_tests()


@pytest.fixture
def reset_settings():
    """Restore `impact_prompt_version` after each test so we don't
    leak state into siblings."""
    settings = get_settings()
    original = settings.impact_prompt_version
    yield settings
    settings.impact_prompt_version = original


def test_v1_loads_v1_prompt_and_suffixes_model(reset_settings):
    reset_settings.impact_prompt_version = "v1"
    a = ImpactAnalyzer()
    assert a.prompt_version == "v1"
    assert a._model.endswith("@v1")
    assert "Market YES price" not in a.system_prompt


def test_v2_loads_v2_prompt_and_suffixes_model(reset_settings):
    reset_settings.impact_prompt_version = "v2"
    a = ImpactAnalyzer()
    assert a.prompt_version == "v2"
    assert a._model.endswith("@v2")
    # The v2 prompt MUST mention "Market YES price" or it's the wrong file.
    assert "Market YES price" in a.system_prompt


def test_unknown_version_falls_back_to_v1(reset_settings, caplog):
    """An operator typo (IMPACT_PROMPT_VERSION=v99) must NOT crash the
    worker on boot — fall back to v1 and log a warning."""
    reset_settings.impact_prompt_version = "v99-typo"
    with caplog.at_level("WARNING"):
        a = ImpactAnalyzer()
    assert any("v99-typo" in rec.message for rec in caplog.records)
    # Loaded a non-empty prompt and didn't crash — that's the contract.
    assert a.system_prompt
    assert a._model.endswith("@v99-typo")  # the label still propagates


@pytest.mark.asyncio
async def test_v1_user_msg_omits_price(reset_settings):
    """v1 receives event + market_question only — the price is dropped
    silently. This pins backward-compat with the legacy prompt."""
    reset_settings.impact_prompt_version = "v1"
    a = ImpactAnalyzer()

    captured = {}

    async def _fake_chat(**kwargs):
        captured["messages"] = kwargs["messages"]
        return '{"impact_direction": "BUY_YES"}'

    with patch.object(a.client, "chat_completion", new=AsyncMock(side_effect=_fake_chat)):
        await a.analyze("Some event", "Some market?", market_yes_price=0.42)

    user_msg = captured["messages"][1]["content"]
    assert "Some market?" in user_msg
    assert "Market YES price" not in user_msg
    assert "0.42" not in user_msg


@pytest.mark.asyncio
async def test_v2_user_msg_includes_price(reset_settings):
    """v2 MUST include the price in the user message — that's the
    whole point of the prompt change."""
    reset_settings.impact_prompt_version = "v2"
    a = ImpactAnalyzer()

    captured = {}

    async def _fake_chat(**kwargs):
        captured["messages"] = kwargs["messages"]
        return '{"impact_direction": "NEUTRAL", "implied_yes_probability": 0.42}'

    with patch.object(a.client, "chat_completion", new=AsyncMock(side_effect=_fake_chat)):
        await a.analyze("Some event", "Some market?", market_yes_price=0.42)

    user_msg = captured["messages"][1]["content"]
    assert "Market YES price" in user_msg
    assert "0.4200" in user_msg


@pytest.mark.asyncio
async def test_v2_missing_price_falls_back_to_05(reset_settings, caplog):
    """Missing price → use 0.50 neutral prior and log. Never crash."""
    reset_settings.impact_prompt_version = "v2"
    a = ImpactAnalyzer()

    captured = {}

    async def _fake_chat(**kwargs):
        captured["messages"] = kwargs["messages"]
        return '{"impact_direction": "NEUTRAL"}'

    with caplog.at_level("INFO"), patch.object(
        a.client, "chat_completion", new=AsyncMock(side_effect=_fake_chat)
    ):
        await a.analyze("Some event", "Some market?", market_yes_price=None)

    user_msg = captured["messages"][1]["content"]
    assert "0.5000" in user_msg
    assert any("missing market_yes_price" in rec.message for rec in caplog.records)
