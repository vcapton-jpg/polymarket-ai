"""Polymarket proxy-Safe address derivation + USDC.e balance reads.

⚠️  CRITICAL — read before touching `compute_safe_address`.

Polymarket users trade through a 1-of-1 Gnosis Safe that Polymarket's
own relayer deploys via Polymarket's OWN proxy factory — *not* the
stock `GnosisSafeProxyFactory.createProxyWithNonce`. The counterfactual
(pre-deploy) address is a CREATE2 of:

    keccak256(0xff ++ factory ++ salt ++ initCodeHash)[12:]
    factory      = 0xaacFeEa03eb1561C4e67d661e40682Bd20E3541b
    salt         = keccak256(abi.encode(address(owner)))
    initCodeHash = 0x2bce2127ff07fb632d16c8347c4ebf501f4841168bed00d9e6ef715ddb6fcecf

This MUST match Polymarket's relayer derivation byte-for-byte. We show
this address to users so they can tip it from Polymarket *before* the
Safe is deployed (P1 onboarding). If our derivation drifts from the
relayer's, a user funds an address the relayer will never deploy → the
tip is stranded. Constants are mirrored from Polymarket's public SDK
`@polymarket/builder-relayer-client` `src/builder/derive.ts`
(`deriveSafe`). Pinned by a concrete test vector in
`tests/unit/test_safe_deployer.py`; verify against a live deploy on
testnet before enabling real-money deposits at scale.

The earlier implementation used the stock Gnosis factory + a saltNonce
derivation. That produced an address Polymarket's relayer would NEVER
deploy and which Polymarket's CLOB would not recognise as the user's
funder — i.e. unusable for trading and unsafe to deposit to. It has
been removed entirely so it cannot be reintroduced by accident.
"""

import asyncio
import logging

from eth_abi import encode
from web3 import Web3

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# ── Polymarket proxy-Safe factory (Polygon mainnet) ──────────────────
# Source: @polymarket/builder-relayer-client src/builder/derive.ts.
# Do NOT swap these for the stock Gnosis SafeProxyFactory / singleton —
# Polymarket's relayer deploys through this specific factory and the
# counterfactual address only matches if these constants match.
_POLYMARKET_SAFE_FACTORY = "0xaacFeEa03eb1561C4e67d661e40682Bd20E3541b"
_POLYMARKET_SAFE_INIT_CODE_HASH = bytes.fromhex(
    "2bce2127ff07fb632d16c8347c4ebf501f4841168bed00d9e6ef715ddb6fcecf"
)


# USDC.e (bridged USDC) on Polygon — the token Polymarket settles in.
# 6 decimals. Reading a balance is a free `eth_call`, no gas, no key.
_USDC_E_POLYGON = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
_USDC_E_DECIMALS = 6
_ERC20_BALANCEOF_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def compute_safe_address(owner_eoa: str) -> str:
    """Deterministic Polymarket proxy-Safe address for `owner_eoa`.

    Pure CREATE2 maths — no network call, no gas, no key, no deploy.
    Must equal the address Polymarket's relayer deploys for this EOA so
    funds tipped here pre-deploy are recoverable at first trade.

    salt = keccak256(abi.encode(owner))            (32-byte padded addr)
    addr = keccak256(0xff ++ factory ++ salt ++ initCodeHash)[-20:]
    """
    owner = Web3.to_checksum_address(owner_eoa)
    salt = Web3.keccak(encode(["address"], [owner]))
    raw = Web3.keccak(
        b"\xff"
        + bytes.fromhex(_POLYMARKET_SAFE_FACTORY[2:])
        + salt
        + _POLYMARKET_SAFE_INIT_CODE_HASH
    )
    return Web3.to_checksum_address("0x" + raw[-20:].hex())


def _usdce_units_to_float(raw: int) -> float:
    """Convert on-chain USDC.e base units (6 decimals) to a float.

    Pure — unit-tested without a network. Kept separate so the RPC
    call and the arithmetic can't drift apart.
    """
    return raw / (10**_USDC_E_DECIMALS)


async def read_usdce_balance(address: str) -> float:
    """Read the USDC.e balance of `address` on Polygon. Free eth_call —
    no gas, no key, no deploy needed (works on a counterfactual Safe
    that hasn't been deployed yet: an undeployed address simply holds
    0, and tokens sent there are recoverable once it deploys)."""
    w3 = Web3(Web3.HTTPProvider(get_settings().polygon_rpc_url))
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(_USDC_E_POLYGON),
        abi=_ERC20_BALANCEOF_ABI,
    )
    loop = asyncio.get_running_loop()
    raw = await loop.run_in_executor(
        None,
        lambda: contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call(),
    )
    return _usdce_units_to_float(int(raw))


class SafeDeployer:
    """Polymarket proxy-Safe deployment.

    The only correct deploy path is Polymarket's gasless relayer (P2 of
    docs/ONBOARDING_BETMOAR_PORT.md), which is not yet implemented. The
    old builder-key path that deployed a stock Gnosis Safe via
    `createProxyWithNonce` has been removed: it deployed at a different
    address than `compute_safe_address` and Polymarket's CLOB would not
    recognise it as the user's funder, so it could only ever strand gas
    and confuse users. `deploy_safe` therefore fails loudly until the
    relayer integration lands.
    """

    def __init__(self):
        self._settings = get_settings()

    async def deploy_safe(self, owner_eoa: str) -> str:
        """Not yet available — see class docstring / P2.

        Raising (rather than silently deploying an incompatible Safe)
        is deliberate: the connect endpoint turns this into a clean 500
        and `native_trading_available` stays False so the frontend
        gates the CTA. Funds can still be received at the
        counterfactual address (`compute_safe_address`) today; only the
        on-chain deploy needs the relayer.
        """
        logger.error(
            "deploy_safe called for %s but the Polymarket relayer deploy "
            "(P2) is not implemented; refusing to deploy an incompatible "
            "stock-Gnosis Safe.",
            owner_eoa,
        )
        raise NotImplementedError(
            "Native Safe deployment is not available yet. Polymarket's "
            "gasless relayer integration (P2) must land first — the "
            "previous builder-key path deployed a Safe at the wrong "
            "address. Funds sent to your deposit address are safe and "
            "will be usable once deployment is enabled."
        )
