"""Daily OpenAI cost watch — T-008 in docs/PLAN_30D_SIGNAL_QUALITY.md.

Three failure modes we want to catch on day-0 instead of at end-of-month:

  1. A prompt regression silently 3x-tokenizes the same payload (the
     2026-04-28 incident: impact_analysis on `gpt-4o` was $27.28 / 7 681
     calls = $0.0035/call, but went to $0.011/call for two days before
     anyone noticed — $50 leaked).
  2. The circuit breaker (`llm_cost_alert_usd=30/24h` in config.py)
     fires AFTER we hit the threshold. We want a leading indicator at
     the half-mark so an operator can intervene before the breaker
     starts dropping live signals.
  3. A new call_type is wired in and grows unbounded because nobody
     budgeted for it. The daily roll-up makes new call_type rows visible
     within 24 h instead of appearing at the bottom of a Stripe receipt
     a month later.

Read-only — no DB writes. Single grouped query, one structured INFO log
line (greppable: `openai.cost.daily`) + optional Telegram alert when
above warning threshold.

Wired into beat at midnight UTC via `cost-watch-daily` in
`app/workers/celery_app.py`.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.database import get_session_factory
from app.db.models import LLMCostLog
from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Telegram alert fires when 24 h spend is at or above this fraction of
# `llm_cost_alert_usd`. 0.5 = "we're halfway to the breaker — investigate
# now". Tunable via env var if 50 % is too jumpy for prod traffic.
_ALERT_FRACTION = 0.5


async def _summarize_last_24h(session_factory) -> dict[str, Any]:
    """Return totals + (call_type, model) breakdown for the last 24 h.

    Shape:
        {
            "window_start": "2026-05-10T00:00:00+00:00",
            "window_end":   "2026-05-11T00:00:00+00:00",
            "total_usd": 12.3456,
            "total_calls": 8412,
            "by_call_type_model": [
                {"call_type": "impact_analysis", "model": "gpt-4o-mini",
                 "calls": 7681, "tokens_in": 12_345_678, "tokens_out": 234_567,
                 "cost_usd": 11.04},
                ...
            ],
        }
    """
    now = datetime.now(UTC)
    window_start = now - timedelta(hours=24)

    async with session_factory() as s:
        rows = (
            await s.execute(
                select(
                    LLMCostLog.call_type,
                    LLMCostLog.model,
                    func.count().label("calls"),
                    func.coalesce(func.sum(LLMCostLog.tokens_input), 0).label("tokens_in"),
                    func.coalesce(func.sum(LLMCostLog.tokens_output), 0).label("tokens_out"),
                    func.coalesce(func.sum(LLMCostLog.cost_usd), 0).label("cost_usd"),
                )
                .where(LLMCostLog.called_at >= window_start)
                .group_by(LLMCostLog.call_type, LLMCostLog.model)
                .order_by(func.sum(LLMCostLog.cost_usd).desc())
            )
        ).all()

    by_call_type_model = [
        {
            "call_type": r.call_type,
            "model": r.model,
            "calls": int(r.calls),
            "tokens_in": int(r.tokens_in),
            "tokens_out": int(r.tokens_out),
            "cost_usd": round(float(r.cost_usd), 4),
        }
        for r in rows
    ]
    total_usd = round(sum(item["cost_usd"] for item in by_call_type_model), 4)
    total_calls = sum(item["calls"] for item in by_call_type_model)

    return {
        "window_start": window_start.isoformat(),
        "window_end": now.isoformat(),
        "total_usd": total_usd,
        "total_calls": total_calls,
        "by_call_type_model": by_call_type_model,
    }


def _format_telegram_alert(summary: dict[str, Any], threshold_usd: float) -> str:
    """Markdown body for the daily-cost Telegram alert (when fired)."""
    lines = [
        "🚨 *OpenAI cost watch* — 24h spend above warning",
        f"Total: *${summary['total_usd']:.2f}* / threshold ${threshold_usd:.2f}",
        f"Calls: {summary['total_calls']:,}",
        "",
        "Top by spend:",
    ]
    for item in summary["by_call_type_model"][:5]:
        lines.append(
            f"• `{item['call_type']}` × `{item['model']}` "
            f"→ ${item['cost_usd']:.2f} ({item['calls']:,} calls)"
        )
    return "\n".join(lines)


async def _maybe_send_telegram_alert(summary: dict[str, Any]) -> bool:
    """Send a Telegram alert when 24 h spend crosses
    `_ALERT_FRACTION × llm_cost_alert_usd`. Returns True if sent."""
    settings = get_settings()
    threshold = float(settings.llm_cost_alert_usd) * _ALERT_FRACTION
    if summary["total_usd"] < threshold:
        return False

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.info(
            "openai.cost.daily.alert SKIP no telegram creds — total=$%.2f threshold=$%.2f",
            summary["total_usd"],
            threshold,
        )
        return False

    from app.telegram.bot import send_message

    body = _format_telegram_alert(summary, threshold)
    sent = await send_message(settings.telegram_chat_id, body, parse_mode="Markdown")
    logger.info(
        "openai.cost.daily.alert SENT=%s total=$%.2f threshold=$%.2f",
        sent,
        summary["total_usd"],
        threshold,
    )
    return sent


async def _emit_daily_cost() -> dict[str, Any]:
    """Compute and log the 24 h LLM-cost summary; optionally Telegram-alert."""
    session_factory = get_session_factory()
    summary = await _summarize_last_24h(session_factory)

    # Single structured log line — greppable as `openai.cost.daily`.
    # Top 3 only so the line stays scannable in `docker compose logs`.
    top3 = summary["by_call_type_model"][:3]
    logger.info(
        "openai.cost.daily total=$%.4f calls=%d top3=%s window=%s..%s",
        summary["total_usd"],
        summary["total_calls"],
        top3,
        summary["window_start"],
        summary["window_end"],
    )

    try:
        await _maybe_send_telegram_alert(summary)
    except Exception as e:
        # Never let an alert-channel failure mask the cost data — the
        # log line above is the source of truth for the operator.
        logger.warning("openai.cost.daily.alert failed: %s: %s", type(e).__name__, e)

    return summary


@celery_app.task(name="app.workers.tasks_costs.emit_daily_cost")
def emit_daily_cost() -> dict[str, Any]:
    return _run_async(_emit_daily_cost())


__all__ = ["emit_daily_cost"]
