"""Tests for `/api/telegram/webhook` shared-secret authentication.

Audit follow-up 2026-05-05 (PR #45 / H2). Pre-PR, the endpoint accepted
any POST and triggered `send_message` toward the chat_id in the
request body — anyone could spoof an `update`, burn the bot quota,
leak `/signals` output to attacker chats, and DoS the worker.

These tests pin three behaviors:
  * No secret configured → handler runs (dev escape hatch).
  * Secret configured + correct header → 200.
  * Secret configured + wrong/missing header → 401, no body, no
    downstream call.

We patch `send_message` and `handle_command` to keep the test offline
and focused on the auth boundary; the bot internals are tested
elsewhere (and out-of-scope for an auth contract test).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _telegram_update(text: str = "/help") -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "chat": {"id": 12345, "type": "private"},
            "text": text,
        },
    }


def test_webhook_503_when_bot_token_unconfigured(client: TestClient):
    """Sanity: with no `TELEGRAM_BOT_TOKEN`, the endpoint short-circuits
    to 503 BEFORE the secret check. Nothing about auth is exercised here
    — included so a future refactor that re-orders the checks doesn't
    accidentally regress this one."""
    fake_settings = type("S", (), {
        "telegram_bot_token": None,
        "telegram_webhook_secret": "any-secret",
    })()
    with patch("app.api.routes.telegram_webhook.get_settings", return_value=fake_settings):
        resp = client.post("/api/telegram/webhook", json=_telegram_update())
    assert resp.status_code == 503


def test_webhook_rejects_request_without_secret_header(client: TestClient):
    """The keystone test — pre-PR #45, this returned 200 (handler ran).
    Post-PR, no header → 401, no body."""
    fake_settings = type("S", (), {
        "telegram_bot_token": "fake-bot-token",
        "telegram_webhook_secret": "secret-should-be-this",
    })()
    with patch("app.api.routes.telegram_webhook.get_settings", return_value=fake_settings), \
         patch("app.api.routes.telegram_webhook.send_message", new_callable=AsyncMock) as send_mock, \
         patch("app.api.routes.telegram_webhook.handle_command", new_callable=AsyncMock) as cmd_mock:
        resp = client.post("/api/telegram/webhook", json=_telegram_update())
    assert resp.status_code == 401
    # Critical — neither side-effect runs.
    send_mock.assert_not_called()
    cmd_mock.assert_not_called()


def test_webhook_rejects_request_with_wrong_secret(client: TestClient):
    fake_settings = type("S", (), {
        "telegram_bot_token": "fake-bot-token",
        "telegram_webhook_secret": "expected-secret",
    })()
    with patch("app.api.routes.telegram_webhook.get_settings", return_value=fake_settings), \
         patch("app.api.routes.telegram_webhook.send_message", new_callable=AsyncMock) as send_mock:
        resp = client.post(
            "/api/telegram/webhook",
            json=_telegram_update(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-value"},
        )
    assert resp.status_code == 401
    send_mock.assert_not_called()


def test_webhook_accepts_request_with_correct_secret(client: TestClient):
    fake_settings = type("S", (), {
        "telegram_bot_token": "fake-bot-token",
        "telegram_webhook_secret": "shared-secret-xyz",
    })()
    with patch("app.api.routes.telegram_webhook.get_settings", return_value=fake_settings), \
         patch(
             "app.api.routes.telegram_webhook.handle_command",
             new_callable=AsyncMock,
             return_value="hello!",
         ) as cmd_mock, \
         patch(
             "app.api.routes.telegram_webhook.send_message", new_callable=AsyncMock
         ) as send_mock:
        resp = client.post(
            "/api/telegram/webhook",
            json=_telegram_update(text="/help"),
            headers={"X-Telegram-Bot-Api-Secret-Token": "shared-secret-xyz"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    cmd_mock.assert_awaited_once()
    send_mock.assert_awaited_once()


def test_webhook_accepts_when_secret_unconfigured_dev_escape_hatch(client: TestClient):
    """Empty `TELEGRAM_WEBHOOK_SECRET` disables the check — intended for
    local dev where you don't want to set up the header dance. This is
    DOCUMENTED in the route's module docstring; it should not regress
    silently."""
    fake_settings = type("S", (), {
        "telegram_bot_token": "fake-bot-token",
        "telegram_webhook_secret": "",  # empty → check disabled
    })()
    with patch("app.api.routes.telegram_webhook.get_settings", return_value=fake_settings), \
         patch(
             "app.api.routes.telegram_webhook.handle_command",
             new_callable=AsyncMock, return_value="ok",
         ), \
         patch("app.api.routes.telegram_webhook.send_message", new_callable=AsyncMock):
        resp = client.post("/api/telegram/webhook", json=_telegram_update())
    assert resp.status_code == 200


def test_webhook_uses_constant_time_comparison():
    """Defensive — the route must use `hmac.compare_digest` and not `==`,
    otherwise a timing oracle leaks the secret one byte at a time. This
    is checked at the source-file level rather than via timing because
    a flake-resistant timing test is impossibly slow.
    """
    import inspect

    from app.api.routes import telegram_webhook

    src = inspect.getsource(telegram_webhook.telegram_webhook)
    assert "hmac.compare_digest" in src, (
        "telegram_webhook handler must use hmac.compare_digest for the "
        "secret comparison; raw `==` exposes a timing oracle."
    )
