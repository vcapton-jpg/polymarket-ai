"""Tests for wallet connect/status endpoints.

Marked `integration` because FastAPI's `TestClient(app)` lifespan
triggers the Celery broker / Redis bootstrap. CI runs unit gate with
`-m "not integration"`; the full suite needs `docker compose up`.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
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
        user = make_user(safe_address="0xExistingSafe000000000000000000000000000000", wallet_address="0xEOA")
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            with patch("app.api.routes.trading_wallet._deployer") as mock_deployer:
                resp = client.post(
                    "/api/trading/wallet/connect",
                    json={"eoa_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"},
                )
            assert resp.status_code == 200
            assert resp.json()["safe_address"] == "0xExistingSafe000000000000000000000000000000"
            mock_deployer.deploy_safe.assert_not_called()
        finally:
            app.dependency_overrides.clear()

    def test_success_deploys_and_stores(self):
        user = make_user()
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            with patch("app.api.routes.trading_wallet._deployer") as mock_deployer:
                mock_deployer.deploy_safe = AsyncMock(
                    return_value="0xNewSafe0000000000000000000000000000000000"
                )
                resp = client.post(
                    "/api/trading/wallet/connect",
                    json={"eoa_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"},
                )
            assert resp.status_code == 200
            assert resp.json()["safe_address"] == "0xNewSafe0000000000000000000000000000000000"
            assert user.polymarket_safe_address == "0xNewSafe0000000000000000000000000000000000"
            db.commit.assert_called_once()
        finally:
            app.dependency_overrides.clear()

    def test_500_on_deploy_failure(self):
        user = make_user()
        db = make_db()

        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_db_session] = lambda: db

        try:
            client = TestClient(app)
            with patch("app.api.routes.trading_wallet._deployer") as mock_deployer:
                mock_deployer.deploy_safe = AsyncMock(
                    side_effect=RuntimeError("Deployment failed")
                )
                resp = client.post(
                    "/api/trading/wallet/connect",
                    json={"eoa_address": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"},
                )
            assert resp.status_code == 500
        finally:
            app.dependency_overrides.clear()
