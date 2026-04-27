"""Audit follow-up [P1]: `_broadcast_signal` reads `signal.created_at`
immediately after `session.flush()`, but Signal.created_at uses
`server_default=func.now()` — meaning Postgres fills it on INSERT but
the Python object stays None until `session.refresh()` (the session
runs with `expire_on_commit=False` so commit alone doesn't reload it).

Result: every WS subscriber received `created_at: null` in the payload
instead of the real timestamp.

Same payload also has a falsy-zero bug at `market_price_at_signal`: a
deeply-NO signal with price=0 was broadcast as `market_price_at_signal:
null`. Mirror of the tasks_scoring [P0] fix.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import delete


@pytest.mark.asyncio
async def test_broadcast_payload_has_real_created_at_and_zero_price(
    async_db_factory,
):
    from app.db.models import Event, Market, Signal
    from app.workers import tasks_scoring as ts

    EVENT_ID = 992200
    MARKET_ID = "0xbroadcast-payload-1"

    async with async_db_factory() as s:
        s.add(Market(market_id=MARKET_ID, question="q", active=True))
        s.add(Event(id=EVENT_ID, event_title="e"))
        await s.commit()

    captured = {}

    def _capture(payload_str):
        import json as _json
        captured["payload"] = _json.loads(payload_str)

    class _FakeAsyncRedis:
        """Async-shaped Redis mock — `_broadcast_signal` was converted
        to async (P0-5 audit fix, 2026-04-27) and now uses
        `redis.asyncio.from_url(...)`."""

        async def publish(self, channel, payload):
            _capture(payload)

        async def aclose(self):
            pass

    try:
        async with async_db_factory() as s:
            sig = Signal(
                event_id=EVENT_ID,
                market_id=MARKET_ID,
                signal_score=72.0,
                signal_strength=72,
                trade_quality=60,
                direction="BUY_NO",
                # PIN: a deeply-NO signal at exactly price=0 must NOT be
                # coerced to null in the broadcast payload. Audit follow-up.
                market_price_at_signal=0.0,
            )
            s.add(sig)
            await s.flush()

            # Audit follow-up [P1]: pipeline must refresh created_at before
            # broadcasting so subscribers get a real timestamp.
            await s.refresh(sig, ["created_at"])

            # Mock just the Redis client, then call the real broadcast.
            with patch(
                "redis.asyncio.from_url", return_value=_FakeAsyncRedis(),
            ):
                await ts._broadcast_signal(sig)
                # Telegram + push are no-ops without configured tokens.

            assert "payload" in captured, "broadcast didn't reach Redis"
            payload = captured["payload"]
            assert payload["created_at"] is not None, (
                "broadcast emitted null created_at — refresh after flush "
                "didn't run (audit follow-up [P1])."
            )
            # ISO-8601 string with tz info or microseconds — sanity check
            assert isinstance(payload["created_at"], str)
            assert payload["created_at"].startswith("20")
            # PIN: zero price must round-trip as 0.0, not null.
            assert payload["market_price_at_signal"] == 0.0, (
                f"zero market_price_at_signal coerced to "
                f"{payload['market_price_at_signal']!r} — "
                "falsy-zero bug at broadcast site."
            )
    finally:
        async with async_db_factory() as s:
            await s.execute(delete(Signal).where(Signal.market_id == MARKET_ID))
            await s.execute(delete(Event).where(Event.id == EVENT_ID))
            await s.execute(delete(Market).where(Market.market_id == MARKET_ID))
            await s.commit()
