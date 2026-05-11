"""Unit tests for the daily OpenAI cost-watch task (T-008).

Covers the pure helpers — `_format_telegram_alert` and the alert
threshold gate inside `_maybe_send_telegram_alert`. The end-to-end
`_emit_daily_cost` flow needs a live DB and is exercised in the
integration suite.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.workers import tasks_costs


def _make_summary(total_usd: float = 25.0, calls: int = 1234) -> dict:
    return {
        "window_start": "2026-05-10T00:00:00+00:00",
        "window_end": "2026-05-11T00:00:00+00:00",
        "total_usd": total_usd,
        "total_calls": calls,
        "by_call_type_model": [
            {
                "call_type": "impact_analysis",
                "model": "gpt-4o-mini",
                "calls": 900,
                "tokens_in": 1_200_000,
                "tokens_out": 80_000,
                "cost_usd": 20.0,
            },
            {
                "call_type": "event_summary",
                "model": "gpt-4o-mini",
                "calls": 334,
                "tokens_in": 50_000,
                "tokens_out": 5_000,
                "cost_usd": 5.0,
            },
        ],
    }


def test_format_telegram_alert_includes_total_threshold_and_top5():
    """Output must surface the headline numbers and the top spenders
    so the on-call sees the cause at a glance."""
    body = tasks_costs._format_telegram_alert(_make_summary(total_usd=25.0), threshold_usd=15.0)
    assert "$25.00" in body
    assert "$15.00" in body
    assert "impact_analysis" in body
    assert "event_summary" in body
    # Top-5 cap exists so the message stays readable on phones — make
    # sure we honor it even if the summary holds 10 rows.
    summary = _make_summary()
    summary["by_call_type_model"] = [
        {
            "call_type": f"ct_{i}",
            "model": "gpt-4o-mini",
            "calls": 100,
            "tokens_in": 1000,
            "tokens_out": 100,
            "cost_usd": 1.0,
        }
        for i in range(10)
    ]
    body = tasks_costs._format_telegram_alert(summary, threshold_usd=10.0)
    assert "ct_0" in body
    assert "ct_4" in body
    assert "ct_5" not in body


@pytest.mark.asyncio
async def test_alert_skipped_below_threshold(monkeypatch):
    """No Telegram call when total_usd is below the fraction-threshold."""
    # llm_cost_alert_usd default = 30.0, _ALERT_FRACTION = 0.5 → fire @ 15.0
    summary = _make_summary(total_usd=10.0)

    mock_send = AsyncMock(return_value=True)
    monkeypatch.setattr("app.telegram.bot.send_message", mock_send)

    sent = await tasks_costs._maybe_send_telegram_alert(summary)
    assert sent is False
    mock_send.assert_not_called()


@pytest.mark.asyncio
async def test_alert_skipped_when_no_creds(monkeypatch):
    """Above-threshold + no Telegram creds → log + return False (no crash)."""
    summary = _make_summary(total_usd=20.0)  # above 15.0 threshold

    # Force telegram creds to None via the cached settings object.
    settings = tasks_costs.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", None)
    monkeypatch.setattr(settings, "telegram_chat_id", None)

    sent = await tasks_costs._maybe_send_telegram_alert(summary)
    assert sent is False


@pytest.mark.asyncio
async def test_alert_sent_when_above_threshold_and_creds_present(monkeypatch):
    """Above-threshold + creds → exactly one `send_message` call with the chat_id."""
    summary = _make_summary(total_usd=20.0)  # above 15.0

    settings = tasks_costs.get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", "fake-bot-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "1234567890")

    mock_send = AsyncMock(return_value=True)
    # Patch on the bot module because tasks_costs imports lazily.
    monkeypatch.setattr("app.telegram.bot.send_message", mock_send)

    sent = await tasks_costs._maybe_send_telegram_alert(summary)
    assert sent is True
    mock_send.assert_awaited_once()
    args, kwargs = mock_send.call_args
    # First positional = chat_id, second = body
    assert args[0] == "1234567890"
    assert "$20.00" in args[1]


@pytest.mark.asyncio
async def test_summarize_last_24h_groups_and_sorts_by_cost(monkeypatch):
    """Pure logic check on the SQL-result shape — no live DB.

    Stub the SQLAlchemy session so we can assert that
    `_summarize_last_24h` rolls the per-(call_type, model) rows into
    the documented dict shape and the top-3 ordering survives.
    """
    fake_rows = [
        type(
            "Row",
            (),
            {
                "call_type": "impact_analysis",
                "model": "gpt-4o-mini",
                "calls": 7681,
                "tokens_in": 12_345_678,
                "tokens_out": 234_567,
                "cost_usd": 11.04,
            },
        )(),
        type(
            "Row",
            (),
            {
                "call_type": "event_summary",
                "model": "gpt-4o-mini",
                "calls": 5027,
                "tokens_in": 200_000,
                "tokens_out": 25_000,
                "cost_usd": 0.52,
            },
        )(),
    ]

    class _FakeResult:
        def all(self):
            return fake_rows

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *args, **kwargs):
            return _FakeResult()

    def _factory():
        return _FakeSession()

    summary = await tasks_costs._summarize_last_24h(_factory)
    assert summary["total_usd"] == round(11.04 + 0.52, 4)
    assert summary["total_calls"] == 7681 + 5027
    assert summary["by_call_type_model"][0]["call_type"] == "impact_analysis"
    assert summary["by_call_type_model"][1]["call_type"] == "event_summary"
