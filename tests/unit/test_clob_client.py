"""Tests for the v2 CLOB client wrapper."""
from unittest.mock import MagicMock, patch
import pytest

from app.trading.builder_client import get_user_clob_client, BuilderTradeClient


def _mock_settings(
    private_key="0xdeadbeef",
    api_key="key",
    api_secret="secret",
    api_passphrase="pass",
    chain_id=137,
    builder_code="0x0000",
):
    s = MagicMock()
    s.builder_private_key = private_key
    s.builder_api_key = api_key
    s.builder_api_secret = api_secret
    s.builder_api_passphrase = api_passphrase
    s.polygon_chain_id = chain_id
    s.polymarket_builder_code = builder_code
    return s


class TestGetUserClobClient:
    @patch("app.trading.builder_client.get_settings")
    @patch("app.trading.builder_client.ClobClient")
    def test_creates_client_with_funder(self, mock_clob_cls, mock_get_settings):
        mock_get_settings.return_value = _mock_settings()
        mock_clob_cls.return_value = MagicMock()
        client = get_user_clob_client("0xSafeAddress")
        call_kwargs = mock_clob_cls.call_args.kwargs
        assert call_kwargs["funder"] == "0xSafeAddress"

    @patch("app.trading.builder_client.get_settings")
    @patch("app.trading.builder_client.ClobClient")
    def test_creates_client_with_key(self, mock_clob_cls, mock_get_settings):
        mock_get_settings.return_value = _mock_settings()
        mock_clob_cls.return_value = MagicMock()
        get_user_clob_client("0xSafe")
        call_kwargs = mock_clob_cls.call_args.kwargs
        assert "key" in call_kwargs


class TestBuilderTradeClientOrders:
    @pytest.mark.asyncio
    @patch("app.trading.builder_client.ClobClient")
    @patch("app.trading.builder_client.get_settings")
    async def test_place_limit_order_uses_side_enum(self, mock_settings, mock_clob_cls):
        mock_settings.return_value.builder_private_key = "0xdeadbeef"
        mock_settings.return_value.polygon_chain_id = 137
        mock_settings.return_value.builder_api_key = None
        mock_settings.return_value.builder_api_secret = None
        mock_settings.return_value.builder_api_passphrase = None
        mock_settings.return_value.polymarket_builder_code = "0x" + "0" * 64
        mock_client = MagicMock()
        mock_client.create_and_post_order.return_value = {"orderID": "abc123", "success": True}
        mock_clob_cls.return_value = mock_client

        trader = BuilderTradeClient("0xSafeAddr")
        result = await trader.place_limit_order("0xtoken", "BUY", 0.5, 10.0)

        assert result["success"] is True
        assert result["order_id"] == "abc123"
        call_args = mock_client.create_and_post_order.call_args[0]
        from py_clob_client_v2.order_utils.model.side import Side
        assert call_args[0].side == Side.BUY
