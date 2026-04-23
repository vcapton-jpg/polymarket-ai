"""Integration tests for GET /api/me/limits — the authoritative endpoint the
frontend consults for budget/cooloff/unlock state.

The route lives next to `/api/me/quota` in `app.api.routes.quota`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.models import UserLimits


@pytest.mark.asyncio
async def test_get_me_limits_returns_seeded_row(async_db_factory, auth_headers_for_user):
    """Hydrates from an existing UserLimits row."""
    uid, headers = await auth_headers_for_user()
    async with async_db_factory() as s:
        s.add(
            UserLimits(
                user_id=uid,
                budget_weekly_eur=50,
                max_stake_eur=10,
                quiz_passed=True,
                age_confirmed_18=True,
                week_spent_eur=12,
            )
        )
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/me/limits", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert float(data["budget_weekly_eur"]) == 50.0
    assert float(data["max_stake_eur"]) == 10.0
    assert float(data["week_spent_eur"]) == 12.0
    assert data["quiz_passed"] is True
    assert data["age_confirmed_18"] is True
    assert data["cooloff_until"] is None


@pytest.mark.asyncio
async def test_get_me_limits_returns_safe_defaults_when_missing(
    auth_headers_for_user,
):
    """Users without a UserLimits row get safe, locked defaults — never a 404."""
    uid, headers = await auth_headers_for_user()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/me/limits", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert float(data["budget_weekly_eur"]) == 20.0
    assert float(data["max_stake_eur"]) == 10.0
    assert data["level"] == 1
    assert data["real_trades_count"] == 0
    assert data["consecutive_losses"] == 0
    assert float(data["week_spent_eur"]) == 0.0
    assert data["cooloff_until"] is None
    # Critical: defaults must keep the user LOCKED until onboarding.
    assert data["quiz_passed"] is False
    assert data["age_confirmed_18"] is False


@pytest.mark.asyncio
async def test_get_me_limits_surfaces_cooloff(async_db_factory, auth_headers_for_user):
    """Cooloff timestamps round-trip through the API (FE renders the pause banner)."""
    uid, headers = await auth_headers_for_user()
    until = (datetime.now(timezone.utc) + timedelta(hours=24)).replace(microsecond=0)
    async with async_db_factory() as s:
        s.add(
            UserLimits(
                user_id=uid,
                budget_weekly_eur=20,
                max_stake_eur=10,
                cooloff_until=until,
                consecutive_losses=3,
            )
        )
        await s.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/me/limits", headers=headers)

    assert r.status_code == 200, r.text
    data = r.json()
    assert data["cooloff_until"] is not None
    assert data["consecutive_losses"] == 3


@pytest.mark.asyncio
async def test_get_me_limits_requires_auth():
    """No bearer token → 401 (not a silent default)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/me/limits")
    assert r.status_code == 401
