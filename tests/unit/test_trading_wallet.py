"""Tests for wallet connect/status endpoints.

Marked `integration` because FastAPI's `TestClient(app)` lifespan
triggers the Celery broker / Redis bootstrap. CI runs unit gate with
`-m "not integration"`; the full suite needs `docker compose up`.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.routes.auth import get_current_user
from app.db.database import get_db_session

pytestmark = pytest.mark.integration


def make_user(safe_address=None, wallet_address=None):
    user = MagicMock()
    user.id = 1
    user.wallet_address = wallet_address
    user.polymarket_safe_address = safe_address
    return user


def make_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    return db


class TestWalletStatus:
    def test_requires_auth(self):
        client = TestClient(app)
        resp = client.get("/api/trading/wallet/status")
        assert resp.status_code in (401, 403)

    def test_returns_not_connected_when_no_safe(self):
        user = make_user()
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get("/api/trading/wallet/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is False
            assert data["safe_address"] is None
        finally:
            app.dependency_overrides.clear()

    def test_returns_connected_when_safe_exists(self):
        user = make_user(safe_address="0xSafe123", wallet_address="0xEOA456")
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            resp = client.get("/api/trading/wallet/status")
            assert resp.status_code == 200
            data = resp.json()
            assert data["connected"] is True
            assert data["safe_address"] == "0xSafe123"
        finally:
            app.dependency_overrides.clear()


class TestWalletConnect:
    def test_400_on_invalid_eoa(self):
        user = make_user()
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            resp = client.post(
                "/api/trading/wallet/connect",
                json={"eoa_address": "not-an-address"},
            )
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()

    def test_idempotent_when_safe_exists(self):
        # Early-return path: user already has a Safe → no nonce, no
        # on-chain check, no deploy. (P2b removed all backend deploy.)
        user = make_user(
            safe_address="0xExistingSafe000000000000000000000000000000",
            wallet_address="0xEOA",
        )
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            resp = client.post(
                "/api/trading/wallet/connect",
                json={"eoa_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"},
            )
            assert resp.status_code == 200
            assert (
                resp.json()["safe_address"]
                == "0xExistingSafe000000000000000000000000000000"
            )
        finally:
            app.dependency_overrides.clear()


# ── P2b /connect: verify-and-record (NO backend deploy) ──────────────
_EOA = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


class _FakeRedis:
    """Minimal async redis stub: nonce present + one-shot delete."""

    def __init__(self, nonce):
        self._nonce = nonce

    async def get(self, _key):
        return self._nonce

    async def delete(self, _key):
        return 1

    async def aclose(self):
        return None


def _connect_overrides(user, db):
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db_session] = lambda: db


class TestConnectVerifyAndRecord:
    """The browser deploys gaslessly via the relayer; /connect proves
    EOA control, derives the Safe, confirms it's on-chain, persists.
    """

    def _post_with_valid_auth(self, deployed, *, rpc_error=False):
        from app.trading.safe_deployer import compute_safe_address

        user = make_user()
        db = make_db()
        _connect_overrides(user, db)
        expected_safe = compute_safe_address(_EOA)
        try:
            client = TestClient(app)
            dep = (
                AsyncMock(side_effect=RuntimeError("rpc down"))
                if rpc_error
                else AsyncMock(return_value=deployed)
            )
            with (
                patch(
                    "app.api.routes.trading_wallet._get_redis",
                    AsyncMock(return_value=_FakeRedis("nonce123")),
                ),
                patch(
                    "app.api.routes.trading_wallet.Account.recover_message",
                    return_value=_EOA,
                ),
                patch(
                    "app.api.routes.trading_wallet.is_contract_deployed", dep
                ),
            ):
                resp = client.post(
                    "/api/trading/wallet/connect",
                    json={
                        "eoa_address": _EOA,
                        "nonce": "nonce123",
                        "signature": "0x" + "ab" * 65,
                    },
                )
            return resp, user, db, expected_safe
        finally:
            app.dependency_overrides.clear()

    def test_400_on_invalid_eoa(self):
        user, db = make_user(), make_db()
        _connect_overrides(user, db)
        try:
            resp = TestClient(app).post(
                "/api/trading/wallet/connect",
                json={"eoa_address": "nope", "nonce": "n", "signature": "0x"},
            )
            assert resp.status_code == 400
        finally:
            app.dependency_overrides.clear()

    def test_200_persists_when_deployed(self):
        resp, user, db, expected_safe = self._post_with_valid_auth(True)
        assert resp.status_code == 200
        assert resp.json()["safe_address"] == expected_safe
        assert user.polymarket_safe_address == expected_safe
        assert user.wallet_address == _EOA
        db.commit.assert_called_once()

    def test_409_when_safe_not_deployed(self):
        resp, user, db, _ = self._post_with_valid_auth(False)
        assert resp.status_code == 409
        db.commit.assert_not_called()

    def test_502_when_rpc_check_fails(self):
        resp, _, db, _ = self._post_with_valid_auth(False, rpc_error=True)
        assert resp.status_code == 502
        db.commit.assert_not_called()
