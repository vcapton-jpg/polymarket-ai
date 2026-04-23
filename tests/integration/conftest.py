"""Integration test helpers for routes that require auth."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import delete

from app.api.routes.auth import _create_token
from app.db.models import UserProfile


@pytest.fixture
async def auth_headers_for_user(async_db_factory):
    """Factory that creates a fresh UserProfile and returns ``(user_id, headers)``.

    Teardown deletes every user this fixture created. Thanks to ``ondelete=CASCADE``
    on ``user_limits.user_id``, ``onboarding_progress.user_id``, ``portfolios.user_id``
    (and orders/positions via their portfolio FK), removing the UserProfile row
    wipes all per-user scaffolding too. Market rows are orthogonal and cleaned
    by the caller or via this fixture's ``markets_to_cleanup`` list.
    """
    created_ids: list[int] = []
    markets_to_cleanup: list[str] = []

    async def _factory(email: str | None = None) -> tuple[int, dict[str, str]]:
        if email is None:
            email = f"trade-test-{uuid.uuid4().hex[:10]}@example.com"
        safe_addr = "0x" + uuid.uuid4().hex[:40].ljust(40, "a")
        async with async_db_factory() as s:
            user = UserProfile(
                email=email,
                plan="free",
                polymarket_safe_address=safe_addr,
            )
            s.add(user)
            await s.commit()
            await s.refresh(user)
            uid = user.id
            created_ids.append(uid)
        token = _create_token(uid)
        return uid, {"Authorization": f"Bearer {token}"}

    # Expose the cleanup list so tests can register markets they create.
    _factory.markets_to_cleanup = markets_to_cleanup  # type: ignore[attr-defined]

    yield _factory

    # Teardown — delete created users (cascades to all per-user rows) and
    # any markets the tests registered for cleanup.
    from app.db.models import Market
    async with async_db_factory() as s:
        if created_ids:
            await s.execute(delete(UserProfile).where(UserProfile.id.in_(created_ids)))
        if markets_to_cleanup:
            await s.execute(delete(Market).where(Market.market_id.in_(markets_to_cleanup)))
        await s.commit()
