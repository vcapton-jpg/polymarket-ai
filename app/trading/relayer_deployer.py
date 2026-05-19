"""Gasless Polymarket Safe deploy via Polymarket's relayer — OPERATOR
self-test path only.

ARCHITECTURE (do not "simplify" this away):

  • The USER-FACING deploy is signed in the user's OWN browser wallet
    (wagmi + @polymarket/builder-relayer-client). The backend never
    holds a user private key and never signs on a user's behalf. That
    flow is P2b (frontend) — not this module.

  • This module is the OPERATOR self-test path: it signs with an
    operator-held key from env (`OPERATOR_TEST_PRIVATE_KEY`) so the
    operator can validate the end-to-end relayer deploy on their OWN
    wallet before the frontend flow ships. It can only ever deploy the
    operator's own Safe.

GATING — three independent locks, all required:
  1. `enable_relayer_deploy` is True (master switch, default False —
     the money switch stays off until the H+72 edge verdict + live-RPC
     verification; see docs/ONBOARDING_BETMOAR_PORT.md).
  2. `operator_test_private_key` is set.
  3. Builder HMAC creds are configured (the relayer requires builder
     attribution headers on /submit — verified in the SDK source).

DEFENSE-IN-DEPTH: before any deploy we assert Polymarket's SDK
`get_expected_safe()` equals our independently-verified
`compute_safe_address()`. A mismatch ABORTS. This is exactly the bug
class that stranded-funds fix #124 addressed — never deploy to an
address we cannot independently reproduce. (The two are already known
to agree: cross-checked against the SDK + Polymarket's own published
test vector.)

The SDK (`py-builder-relayer-client`, sync/`requests`-based) is
lazy-imported and every network call is run in a thread executor so
this stays drop-in for the async app.
"""

from __future__ import annotations

import asyncio
import logging

from eth_account import Account
from web3 import Web3

from app.core.config import get_settings
from app.trading.safe_deployer import compute_safe_address

logger = logging.getLogger(__name__)

# How long to wait for the relayer to land the deploy on-chain before
# giving up. We poll the relayer's own /deployed (authoritative) rather
# than trust an opaque response object.
_DEPLOY_POLL_INTERVAL_S = 3
_DEPLOY_POLL_TIMEOUT_S = 90


class RelayerError(RuntimeError):
    """Base for relayer-deploy failures."""


class RelayerNotEnabled(RelayerError):
    """Gating not satisfied (switch off / no operator key / no creds)."""


class RelayerAddressMismatch(RelayerError):
    """SDK-derived Safe ≠ our compute_safe_address. Hard abort —
    deploying here would risk stranding funds (the #124 bug class)."""


class RelayerDeployer:
    """Operator-only gasless Safe deploy. See module docstring."""

    def __init__(self) -> None:
        self._settings = get_settings()

    # ── gating ───────────────────────────────────────────────────────
    def _operator_address(self) -> str:
        key = self._settings.operator_test_private_key
        if not key:
            raise RelayerNotEnabled(
                "operator_test_private_key not set — this is the "
                "operator self-test path; it never signs for a user."
            )
        return Account.from_key(key).address

    def _assert_ready(self) -> None:
        s = self._settings
        if not s.enable_relayer_deploy:
            raise RelayerNotEnabled(
                "enable_relayer_deploy is False — the gasless deploy "
                "money switch is intentionally off (H+72 gate)."
            )
        if not s.operator_test_private_key:
            raise RelayerNotEnabled(
                "operator_test_private_key not set."
            )
        if not (
            s.builder_api_key
            and s.builder_api_secret
            and s.builder_api_passphrase
        ):
            raise RelayerNotEnabled(
                "Builder HMAC creds incomplete — the relayer requires "
                "builder attribution headers on /submit."
            )

    # ── SDK plumbing ─────────────────────────────────────────────────
    def _build_client(self):
        """Lazy-import + construct the relayer client.

        Lazy because the SDK is a pinned pre-release and only needed
        when the (gated) path actually runs — mirrors the existing
        polymarket_signing.py pattern.
        """
        try:
            from py_builder_relayer_client.client import RelayClient
            from py_builder_signing_sdk.config import BuilderConfig
            from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
        except ImportError as exc:  # pragma: no cover - env guard
            raise RelayerError(
                "py-builder-relayer-client / py-builder-signing-sdk not "
                "installed in this environment."
            ) from exc

        s = self._settings
        builder_config = BuilderConfig(
            local_builder_creds=BuilderApiKeyCreds(
                key=s.builder_api_key,
                secret=s.builder_api_secret,
                passphrase=s.builder_api_passphrase,
            )
        )
        return RelayClient(
            s.relayer_url,
            s.polygon_chain_id,
            s.operator_test_private_key,
            builder_config,
        )

    def _cross_check(self, client) -> str:
        """Assert SDK-expected Safe == our compute_safe_address.

        Returns the (agreed) checksummed Safe address. Raises
        RelayerAddressMismatch otherwise — we never deploy to an
        address we can't independently reproduce.
        """
        operator = self._operator_address()
        ours = compute_safe_address(operator)
        sdk = client.get_expected_safe()
        if Web3.to_checksum_address(sdk) != Web3.to_checksum_address(ours):
            raise RelayerAddressMismatch(
                f"SDK expected_safe={sdk} != compute_safe_address={ours} "
                f"for operator {operator} — aborting (funds-safety)."
            )
        return Web3.to_checksum_address(ours)

    # ── public API (operator self-test) ──────────────────────────────
    async def is_operator_safe_deployed(self) -> bool:
        """True if the operator's Safe already has on-chain code,
        per the relayer's authoritative /deployed. No gating beyond a
        configured operator key (read-only, no funds risk)."""
        client = self._build_client()
        safe = self._cross_check(client)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, lambda: bool(client.get_deployed(safe))
        )

    async def deploy_operator_safe(self) -> str:
        """Gaslessly deploy the OPERATOR's Safe via the relayer.

        Idempotent: returns the address without re-submitting if the
        Safe is already deployed. Raises RelayerNotEnabled if any of
        the three gates is unmet, RelayerAddressMismatch on a
        derivation disagreement, RelayerError if the relayer never
        confirms the deploy on-chain.
        """
        self._assert_ready()
        client = self._build_client()
        safe = self._cross_check(client)
        loop = asyncio.get_running_loop()

        if await loop.run_in_executor(
            None, lambda: bool(client.get_deployed(safe))
        ):
            logger.info("Operator Safe already deployed at %s", safe)
            return safe

        logger.info("Submitting gasless relayer deploy for Safe %s", safe)
        resp = await loop.run_in_executor(None, client.deploy)
        logger.info("Relayer accepted deploy submission: %r", resp)

        # Poll the relayer's authoritative /deployed rather than trust
        # the opaque response object — we only declare success when
        # on-chain code exists.
        waited = 0
        while waited < _DEPLOY_POLL_TIMEOUT_S:
            await asyncio.sleep(_DEPLOY_POLL_INTERVAL_S)
            waited += _DEPLOY_POLL_INTERVAL_S
            if await loop.run_in_executor(
                None, lambda: bool(client.get_deployed(safe))
            ):
                logger.info("Operator Safe deployed at %s (%ss)", safe, waited)
                return safe

        raise RelayerError(
            f"Relayer deploy not confirmed for {safe} after "
            f"{_DEPLOY_POLL_TIMEOUT_S}s (submission resp={resp!r}). "
            f"Re-query /deployed before any retry — re-submitting a "
            f"deployed Safe will error."
        )
