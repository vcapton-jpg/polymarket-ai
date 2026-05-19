"""Gnosis Safe proxy deployment on Polygon mainnet."""

import asyncio
import logging

from eth_abi import encode
from eth_account import Account
from web3 import Web3

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SETUP_SELECTOR = Web3.keccak(
    text="setup(address[],uint256,address,bytes,address,address,uint256,address)"
)[:4]

_PROXY_FACTORY_ABI = [
    {
        "inputs": [
            {"name": "_masterCopy", "type": "address"},
            {"name": "initializer", "type": "bytes"},
            {"name": "saltNonce", "type": "uint256"},
        ],
        "name": "createProxyWithNonce",
        "outputs": [{"name": "proxy", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# GnosisSafeProxy v1.3 creation bytecode (fixed, embeds singleton address at deploy time)
_PROXY_CREATION_CODE = bytes.fromhex(
    "608060405234801561001057600080fd5b506040516101e63803806101e68339"
    "8101604081905261002f91610054565b6001600160a01b03811660009081526020"
    "8190526040902060010155610084565b60006020828403121561006657600080fd5b"
    "81516001600160a01b038116811461007d57600080fd5b9392505050565b60e06100"
    "928339019056fe"
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


def _build_setup_data(owner_eoa: str) -> bytes:
    """Build the initializer bytes for a 1-of-1 Safe owned by owner_eoa."""
    zero = "0x0000000000000000000000000000000000000000"
    args = encode(
        ["address[]", "uint256", "address", "bytes", "address", "address", "uint256", "address"],
        [[Web3.to_checksum_address(owner_eoa)], 1, zero, b"", zero, zero, 0, zero],
    )
    return _SETUP_SELECTOR + args


def compute_safe_address(owner_eoa: str, singleton: str, factory: str | None = None) -> str:
    """Compute the deterministic Safe address for an EOA (no network call).

    Uses CREATE2 with saltNonce = int(owner_eoa, 16) % 2**256.
    """
    if factory is None:
        factory = get_settings().gnosis_safe_proxy_factory

    init_data = _build_setup_data(owner_eoa)
    salt_nonce = int(owner_eoa, 16) % (2**256)

    init_hash = Web3.keccak(init_data)
    salt = Web3.keccak(encode(["bytes32", "uint256"], [init_hash, salt_nonce]))

    proxy_init = _PROXY_CREATION_CODE + encode(
        ["address"], [Web3.to_checksum_address(singleton)]
    )
    proxy_init_hash = Web3.keccak(proxy_init)

    raw = Web3.keccak(
        b"\xff"
        + bytes.fromhex(factory[2:])
        + salt
        + proxy_init_hash
    )
    return Web3.to_checksum_address("0x" + raw[-20:].hex())


class SafeDeployer:
    """Deploys Gnosis Safe proxies on Polygon mainnet."""

    def __init__(self):
        self._settings = get_settings()
        self._w3: Web3 | None = None

    def _get_w3(self) -> Web3:
        if self._w3 is None:
            self._w3 = Web3(Web3.HTTPProvider(self._settings.polygon_rpc_url))
        return self._w3

    async def deploy_safe(self, owner_eoa: str) -> str:
        """Deploy a 1-of-1 Safe for owner_eoa and return its address.

        Idempotent: returns address without re-deploying if already deployed.
        """
        if not self._settings.builder_private_key:
            raise RuntimeError(
                "BUILDER_PRIVATE_KEY not configured — cannot deploy Safes"
            )
        singleton = self._settings.gnosis_safe_singleton
        safe_addr = compute_safe_address(
            owner_eoa, singleton, factory=self._settings.gnosis_safe_proxy_factory
        )

        w3 = self._get_w3()
        loop = asyncio.get_running_loop()

        code = await loop.run_in_executor(None, lambda: w3.eth.get_code(safe_addr))
        if code and code not in (b"", b"\x00"):
            logger.info("Safe already deployed at %s", safe_addr)
            return safe_addr

        factory = w3.eth.contract(
            address=self._settings.gnosis_safe_proxy_factory,
            abi=_PROXY_FACTORY_ABI,
        )
        deployer = Account.from_key(self._settings.builder_private_key)
        init_data = _build_setup_data(owner_eoa)
        salt_nonce = int(owner_eoa, 16) % (2**256)

        nonce = await loop.run_in_executor(
            None, lambda: w3.eth.get_transaction_count(deployer.address)
        )
        gas_price = await loop.run_in_executor(None, lambda: w3.eth.gas_price)

        tx = factory.functions.createProxyWithNonce(
            self._settings.gnosis_safe_singleton,
            init_data,
            salt_nonce,
        ).build_transaction({
            "from": deployer.address,
            "nonce": nonce,
            "gasPrice": int(gas_price * 1.1),
            "gas": 300_000,
            "chainId": self._settings.polygon_chain_id,
        })

        signed = deployer.sign_transaction(tx)
        tx_hash = await loop.run_in_executor(
            None, lambda: w3.eth.send_raw_transaction(signed.raw_transaction)
        )
        logger.info("Safe deployment tx: %s for owner %s", tx_hash.hex(), owner_eoa)

        receipt = await loop.run_in_executor(
            None, lambda: w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        )
        if receipt["status"] != 1:
            raise RuntimeError(f"Safe deployment failed: tx {tx_hash.hex()}")

        logger.info("Safe deployed at %s (owner: %s)", safe_addr, owner_eoa)
        return safe_addr
