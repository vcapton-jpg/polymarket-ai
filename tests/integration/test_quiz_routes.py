"""Integration tests for /api/quiz/* routes."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import app
from app.db.models import OnboardingProgress, QuizAttempt, UserLimits


@pytest.mark.asyncio
async def test_get_quiz_returns_3_questions(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/api/quiz/questions", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert "id" in q and "question" in q and "choices" in q
        assert len(q["choices"]) == 3


@pytest.mark.asyncio
async def test_quiz_pass_unlocks_flag(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/quiz/submit",
            headers=headers,
            json={
                "answers": {
                    "q1_loss_risk": 2,
                    "q2_signal_meaning": 1,
                    "q3_budget_rule": 1,
                },
            },
        )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["passed"] is True
    assert data["score"] == 3
    assert data["total"] == 3

    async with async_db_factory() as s:
        limits = await s.get(UserLimits, uid)
        onb = await s.get(OnboardingProgress, uid)
    assert limits is not None and limits.quiz_passed is True
    assert onb is not None and onb.quiz_done is True


@pytest.mark.asyncio
async def test_quiz_fail_does_not_unlock(async_db_factory, auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post(
            "/api/quiz/submit",
            headers=headers,
            json={
                "answers": {
                    "q1_loss_risk": 0,
                    "q2_signal_meaning": 0,
                    "q3_budget_rule": 0,
                },
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["passed"] is False
    assert r.json()["score"] == 0

    async with async_db_factory() as s:
        limits = await s.get(UserLimits, uid)
    # Either no row or row with quiz_passed=False
    assert limits is None or limits.quiz_passed is False


@pytest.mark.asyncio
async def test_quiz_attempt_row_always_inserted(async_db_factory, auth_headers_for_user):
    """Each submit (pass or fail) must leave a QuizAttempt audit row."""
    from sqlalchemy import select

    uid, headers = await auth_headers_for_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        # Fail first
        await c.post(
            "/api/quiz/submit",
            headers=headers,
            json={
                "answers": {
                    "q1_loss_risk": 0,
                    "q2_signal_meaning": 0,
                    "q3_budget_rule": 0,
                },
            },
        )
        # Then pass
        await c.post(
            "/api/quiz/submit",
            headers=headers,
            json={
                "answers": {
                    "q1_loss_risk": 2,
                    "q2_signal_meaning": 1,
                    "q3_budget_rule": 1,
                },
            },
        )

    async with async_db_factory() as s:
        rows = (
            await s.execute(select(QuizAttempt).where(QuizAttempt.user_id == uid))
        ).scalars().all()
    assert len(rows) == 2
    scores = sorted([r.score for r in rows])
    assert scores == [0, 3]
