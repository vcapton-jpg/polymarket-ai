"""Pin the Polymarket proxy-Safe address derivation (no network).

WHY THIS IS A HARD TEST: we show `compute_safe_address(eoa)` to users
as their deposit address *before* the Safe is deployed (P1 onboarding).
It must equal the address Polymarket's relayer will deploy for that
EOA. A drift here = user tips a Polymarket address the relayer never
deploys = stranded funds. The previous derivation (stock Gnosis
factory + saltNonce) was wrong; these tests lock the corrected
CREATE2(factory, keccak256(abi.encode(owner)), initCodeHash) formula.

`test_matches_polymarket_sdk_vector` is the authoritative check: the
(owner -> safe) pair is lifted verbatim from Polymarket's OWN SDK test
suite `Polymarket/py-builder-relayer-client`
`tests/builder/test_derive.py::test_derive_safe`. Our output matches it
byte-for-byte (including the intermediate salt), so this is "matches
Polymarket", not merely "we didn't change it".

⚠️  There are TWO Polymarket wallet systems. We implement the **Safe**
path (factory 0xaacFeEa0…, `deriveSafe`, abi.encode/padded salt) used
by browser wallets (MetaMask/Rainbow/Coinbase) — which is how this app
signs in (wagmi `useAccount`). The *other* system (factory
0xaB45c5A4…, `deriveProxyWallet`, encodePacked salt) is for Magic/email
accounts and derives a DIFFERENT address. If email login is ever added,
the derivation MUST branch. See docs/ONBOARDING_BETMOAR_PORT.md.
"""

import pytest

from app.trading.safe_deployer import (
    _POLYMARKET_SAFE_FACTORY,
    _POLYMARKET_SAFE_INIT_CODE_HASH,
    SafeDeployer,
    compute_safe_address,
)

# Authoritative: lifted verbatim from Polymarket's own SDK test
# Polymarket/py-builder-relayer-client tests/builder/test_derive.py
# (test_derive_safe). Our compute_safe_address reproduces both the
# intermediate salt (0xd9d34def…) and this final address exactly.
_POLYMARKET_SDK_VECTOR = (
    "0x6e0c80c90ea6c15917308F820Eac91Ce2724B5b5",  # owner EOA
    "0x6d8c4e9aDF5748Af82Dabe2C6225207770d6B4fa",  # expected Safe
)

# Canonical Hardhat/Anvil test EOAs → address our corrected formula
# derives. Self-consistent regression guard (catches any accidental
# change to the formula/constants) on top of the authoritative vector.
_REGRESSION_VECTORS = {
    "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266": "0xd93B25cb943D14d0d34FBaF01Fc93a0f8b5F6E47",
    "0x70997970C51812dc3A010C7d01b50e0d17dc79C8": "0x8ac5D4Bd2752AFc9F5CA531f19D617647216B893",
    "0x2546BcD3c84621e976D8185a91A922aE77ECEc30": "0x6E31a42Bd7E1B8b9cD1471384a0D5191075EAc7B",
}


class TestComputeSafeAddress:
    def test_returns_checksummed_address(self):
        addr = compute_safe_address("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
        assert addr.startswith("0x")
        assert len(addr) == 42
        # Checksummed (mixed case), not all-lower / all-upper.
        assert addr != addr.lower()
        assert addr != addr.upper()

    def test_deterministic_for_same_eoa(self):
        eoa = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        assert compute_safe_address(eoa) == compute_safe_address(eoa)

    def test_input_case_insensitive(self):
        # An EOA passed lower-case must derive the same Safe as the
        # checksummed form — both are the same account.
        lower = "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266"
        mixed = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        assert compute_safe_address(lower) == compute_safe_address(mixed)

    def test_different_for_different_eoa(self):
        a = compute_safe_address("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266")
        b = compute_safe_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8")
        assert a != b

    def test_matches_polymarket_sdk_vector(self):
        """The one that actually proves correctness vs Polymarket.

        Source: Polymarket/py-builder-relayer-client
        tests/builder/test_derive.py::test_derive_safe.
        """
        owner, expected_safe = _POLYMARKET_SDK_VECTOR
        assert compute_safe_address(owner) == expected_safe

    @pytest.mark.parametrize(("eoa", "expected"), _REGRESSION_VECTORS.items())
    def test_known_vectors(self, eoa, expected):
        assert compute_safe_address(eoa) == expected

    def test_uses_polymarket_factory_not_stock_gnosis(self):
        # Guard against a regression to the stock Gnosis factory, which
        # would silently strand user deposits.
        assert _POLYMARKET_SAFE_FACTORY == (
            "0xaacFeEa03eb1561C4e67d661e40682Bd20E3541b"
        )
        assert _POLYMARKET_SAFE_INIT_CODE_HASH.hex() == (
            "2bce2127ff07fb632d16c8347c4ebf501f4841168bed00d9e6ef715ddb6fcecf"
        )
        # The old wrong factory must never come back.
        assert _POLYMARKET_SAFE_FACTORY != (
            "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
        )


class TestDeploySafeIsGuarded:
    """The stock-Gnosis builder-key deploy was removed (wrong address).
    deploy_safe must fail loudly until the relayer (P2) lands rather
    than deploy a Safe at an address Polymarket won't recognise.
    """

    @pytest.mark.asyncio
    async def test_deploy_safe_raises_not_implemented(self):
        deployer = SafeDeployer()
        with pytest.raises(NotImplementedError):
            await deployer.deploy_safe(
                "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
            )
