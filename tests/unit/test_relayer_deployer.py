"""P2 gasless relayer deploy — gating + funds-safety + real-SDK cross-check.

The headline test is `test_real_sdk_matches_our_derivation`: it runs
Polymarket's ACTUAL SDK (`RelayClient.get_expected_safe`, an offline
pure CREATE2 derivation) and asserts it equals our
`compute_safe_address`. That independently re-validates the #124
stranded-funds fix against Polymarket's own live code, in CI, forever.

Everything else proves the operator path stays locked: three gates
(master switch / operator key / builder creds), the address-mismatch
hard-abort, and idempotency.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.trading.relayer_deployer import (
    RelayerAddressMismatch,
    RelayerDeployer,
    RelayerNotEnabled,
)
from app.trading.safe_deployer import compute_safe_address

# Hardhat account #0 — the well-known public test key (also the key in
# Polymarket's own SDK fixtures). Never holds real funds.
_HARDHAT_PK = (
    "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
)
_HARDHAT_ADDR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"


def _settings(**over):
    base = dict(
        enable_relayer_deploy=True,
        operator_test_private_key=_HARDHAT_PK,
        builder_api_key="bk",
        builder_api_secret="bs",
        builder_api_passphrase="bp",
        relayer_url="https://relayer-v2.polymarket.com",
        polygon_chain_id=137,
    )
    base.update(over)
    return SimpleNamespace(**base)


def _deployer(**over):
    d = RelayerDeployer()
    d._settings = _settings(**over)
    return d


class TestRealSdkCrossCheck:
    def test_real_sdk_matches_our_derivation(self):
        # Polymarket's official SDK, offline pure derivation.
        from py_builder_relayer_client.client import RelayClient

        client = RelayClient(
            "https://relayer-v2.polymarket.com", 137, _HARDHAT_PK
        )
        sdk_safe = client.get_expected_safe()
        ours = compute_safe_address(_HARDHAT_ADDR)
        assert sdk_safe.lower() == ours.lower()

    def test_cross_check_passes_with_real_sdk(self):
        # The deployer's own _cross_check against the real SDK client.
        d = _deployer()
        from py_builder_relayer_client.client import RelayClient

        client = RelayClient(
            "https://relayer-v2.polymarket.com", 137, _HARDHAT_PK
        )
        assert d._cross_check(client) == compute_safe_address(_HARDHAT_ADDR)


class TestGating:
    @pytest.mark.asyncio
    async def test_blocked_when_switch_off(self):
        d = _deployer(enable_relayer_deploy=False)
        with pytest.raises(RelayerNotEnabled, match="enable_relayer_deploy"):
            await d.deploy_operator_safe()

    @pytest.mark.asyncio
    async def test_blocked_without_operator_key(self):
        d = _deployer(operator_test_private_key=None)
        with pytest.raises(RelayerNotEnabled, match="operator_test_private_key"):
            await d.deploy_operator_safe()

    @pytest.mark.asyncio
    async def test_blocked_without_builder_creds(self):
        d = _deployer(builder_api_secret=None)
        with pytest.raises(RelayerNotEnabled, match="Builder HMAC creds"):
            await d.deploy_operator_safe()


class TestAddressMismatchAborts:
    @pytest.mark.asyncio
    async def test_mismatch_hard_aborts_before_deploy(self):
        d = _deployer()
        bad_client = MagicMock()
        # SDK disagrees with our derivation → must abort, never deploy.
        bad_client.get_expected_safe.return_value = (
            "0xdeadBEEF00000000000000000000000000000000"
        )
        with (
            patch.object(d, "_build_client", return_value=bad_client),
            pytest.raises(RelayerAddressMismatch),
        ):
            await d.deploy_operator_safe()
        bad_client.deploy.assert_not_called()


class TestIdempotent:
    @pytest.mark.asyncio
    async def test_already_deployed_returns_without_submitting(self):
        d = _deployer()
        expected = compute_safe_address(_HARDHAT_ADDR)
        client = MagicMock()
        client.get_expected_safe.return_value = expected
        client.get_deployed.return_value = True
        with patch.object(d, "_build_client", return_value=client):
            result = await d.deploy_operator_safe()
        assert result == expected
        client.deploy.assert_not_called()


class TestHappyPathPollsAuthoritativeDeployed:
    @pytest.mark.asyncio
    async def test_deploy_then_confirmed_via_get_deployed(self):
        d = _deployer()
        expected = compute_safe_address(_HARDHAT_ADDR)
        client = MagicMock()
        client.get_expected_safe.return_value = expected
        # Not deployed at first check, deployed after relayer submit.
        client.get_deployed.side_effect = [False, True]
        client.deploy.return_value = {"transactionID": "abc"}
        with (
            patch.object(d, "_build_client", return_value=client),
            patch("asyncio.sleep", new=AsyncMock()),
        ):
            result = await d.deploy_operator_safe()
        assert result == expected
        client.deploy.assert_called_once()


class TestSettingsDefaults:
    def test_money_switch_off_and_prod_url_by_default(self):
        from app.core.config import Settings

        s = Settings()
        assert s.enable_relayer_deploy is False
        assert s.relayer_url == "https://relayer-v2.polymarket.com"
        assert s.operator_test_private_key is None
