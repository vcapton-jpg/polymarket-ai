# Polymarket Wallet Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-builder-wallet trading architecture with per-user Gnosis Safe trading: users connect MetaMask once, backend deploys their Safe, all subsequent orders are placed server-side with zero wallet interaction.

**Architecture:** The `ClobClient` from `py_clob_client_v2` accepts a `funder` param — the builder key signs every order, but USDC comes from the user's Safe address. User connects MetaMask once to register their EOA; the backend deploys a minimal Gnosis Safe proxy for that EOA; all future orders call `ClobClient(key=builder_pk, funder=user.polymarket_safe_address)`.

**Tech Stack:** `py_clob_client_v2`, `web3>=6.0` (Safe deployment), `wagmi@2` + `viem@2` (MetaMask connection), FastAPI, SQLAlchemy/Alembic, React 18

---

## File Map

**Create:**
- `app/trading/safe_deployer.py` — deploys Gnosis Safe proxy for a user EOA via web3.py
- `app/api/routes/trading_wallet.py` — `POST /api/trading/wallet/connect`, `GET /api/trading/wallet/status`
- `frontend/src/lib/api/wallet.ts` — typed fetch wrappers for wallet endpoints
- `frontend/src/hooks/useWalletSetup.ts` — wallet state + connect flow
- `frontend/src/components/trading/WalletSetupModal.tsx` — 3-step setup UI
- `tests/unit/test_safe_deployer.py` — unit tests for Safe address computation
- `tests/unit/test_trading_wallet.py` — unit tests for wallet API routes

**Modify:**
- `pyproject.toml` — add `py_clob_client_v2`, `web3>=6.0`; remove `py-clob-client`
- `app/core/config.py` — add `polymarket_builder_code`, `polygon_rpc_url`, Safe contract addresses
- `app/db/models.py` — add `polymarket_safe_address` to `UserProfile`
- `alembic/versions/` — new migration `013_polymarket_safe_address.py`
- `app/trading/builder_client.py` — migrate from v1 to v2 API (`OrderArgsV2`, `Side`, `PartialCreateOrderOptions`), add `get_user_clob_client(safe_address)`
- `app/api/routes/trading.py` — add auth dependency, switch to per-user client
- `app/api/main.py` — register new `trading_wallet` router
- `frontend/package.json` — add `wagmi`, `viem`, `@wagmi/connectors`
- `frontend/src/main.tsx` — wrap app in `WagmiProvider`
- `frontend/src/components/signals/OrderForm.tsx` — gate on wallet setup

---

## Task 1: Backend deps + config

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/core/config.py`

- [ ] **Step 1: Update pyproject.toml**

Replace `py-clob-client>=0.1.0` with the v2 package and add web3. In `pyproject.toml`, find the `# Trading / Business` block and replace it:

```toml
    # Trading / Business
    "py_clob_client_v2>=0.1.0",
    "py-order-utils>=0.1.0",
    "web3>=6.0.0",
    "eth-account>=0.13.0",
```

Remove `"py-clob-client>=0.1.0",` from the list.

- [ ] **Step 2: Add config fields to `app/core/config.py`**

Add inside the `Settings` class, after the existing `builder_private_key` block:

```python
    # Polymarket Builder attribution code (bytes32 hex from polymarket.com/settings?tab=builder)
    polymarket_builder_code: str = Field(
        default="0x0000000000000000000000000000000000000000000000000000000000000000",
        description="Builder attribution code — 66-char hex bytes32",
    )

    # Polygon RPC for Safe deployment
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon mainnet JSON-RPC endpoint",
    )

    # Gnosis Safe contract addresses on Polygon mainnet
    gnosis_safe_proxy_factory: str = Field(
        default="0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2",
        description="GnosisSafeProxyFactory address on Polygon",
    )
    gnosis_safe_singleton: str = Field(
        default="0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552",
        description="GnosisSafe singleton (master copy) on Polygon",
    )
```

- [ ] **Step 3: Install deps**

```bash
cd /Users/vadim/polymarket-ai
pip install py_clob_client_v2 "web3>=6.0.0"
```

Expected: both packages install without errors.

- [ ] **Step 4: Verify imports work**

```bash
python -c "from py_clob_client_v2.client import ClobClient; from py_clob_client_v2.clob_types import OrderArgs, MarketOrderArgs, ApiCreds, Side, OrderType, PartialCreateOrderOptions; print('v2 ok')"
python -c "from web3 import Web3; print('web3 ok')"
```

Expected: `v2 ok` and `web3 ok` printed.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add pyproject.toml app/core/config.py
git commit -m "feat(trading): add py_clob_client_v2 + web3 deps, builder config fields"
```

---

## Task 2: Database migration

**Files:**
- Modify: `app/db/models.py`
- Create: `alembic/versions/013_polymarket_safe_address.py`

- [ ] **Step 1: Add column to UserProfile model**

In `app/db/models.py`, find the `UserProfile` class. After the `wallet_address` line, add:

```python
    polymarket_safe_address: Mapped[Optional[str]] = mapped_column(
        String(42), nullable=True, unique=True
    )
```

- [ ] **Step 2: Generate migration**

```bash
cd /Users/vadim/polymarket-ai
alembic revision --autogenerate -m "add polymarket_safe_address to user_profiles"
```

Expected: new file created at `alembic/versions/013_add_polymarket_safe_address*.py`.

- [ ] **Step 3: Verify migration file**

Open the generated file. Confirm it contains:

```python
op.add_column('user_profiles', sa.Column('polymarket_safe_address', sa.String(length=42), nullable=True))
op.create_unique_constraint(None, 'user_profiles', ['polymarket_safe_address'])
```

If the autogenerate missed the unique constraint, add it manually.

- [ ] **Step 4: Run migration**

```bash
alembic upgrade head
```

Expected: `Running upgrade ... -> ..., add polymarket_safe_address to user_profiles`

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py alembic/versions/
git commit -m "feat(db): add polymarket_safe_address to user_profiles"
```

---

## Task 3: Safe deployer service

**Files:**
- Create: `app/trading/safe_deployer.py`
- Create: `tests/unit/test_safe_deployer.py`

The Gnosis Safe Proxy Factory deploys a proxy using `createProxyWithNonce(address _masterCopy, bytes calldata initializer, uint256 saltNonce)`. The `initializer` is an ABI-encoded call to `setup(address[] owners, uint256 threshold, ...)`.

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_safe_deployer.py`:

```python
"""Tests for Safe address computation (no network calls)."""
import pytest
from unittest.mock import MagicMock, patch

from app.trading.safe_deployer import compute_safe_address, SafeDeployer


class TestComputeSafeAddress:
    def test_returns_checksummed_address(self):
        eoa = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        addr = compute_safe_address(eoa, singleton="0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552")
        assert addr.startswith("0x")
        assert len(addr) == 42

    def test_deterministic_for_same_eoa(self):
        eoa = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
        singleton = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
        assert compute_safe_address(eoa, singleton) == compute_safe_address(eoa, singleton)

    def test_different_for_different_eoa(self):
        singleton = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
        addr1 = compute_safe_address("0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266", singleton)
        addr2 = compute_safe_address("0x70997970C51812dc3A010C7d01b50e0d17dc79C8", singleton)
        assert addr1 != addr2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/vadim/polymarket-ai
pytest tests/unit/test_safe_deployer.py -v
```

Expected: `ImportError: cannot import name 'compute_safe_address' from 'app.trading.safe_deployer'`

- [ ] **Step 3: Implement `app/trading/safe_deployer.py`**

```python
"""Gnosis Safe proxy deployment on Polygon mainnet."""

import logging
from typing import Optional

from eth_abi import encode
from eth_account import Account
from web3 import Web3

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# GnosisSafe.setup() selector
_SETUP_SELECTOR = Web3.keccak(
    text="setup(address[],uint256,address,bytes,address,address,uint256,address)"
)[:4]

# ProxyFactory.createProxyWithNonce() ABI (minimal)
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
    {
        "inputs": [
            {"name": "_masterCopy", "type": "address"},
            {"name": "initializer", "type": "bytes"},
            {"name": "saltNonce", "type": "uint256"},
        ],
        "name": "calculateCreateProxyWithNonceAddress",
        "outputs": [{"name": "proxy", "type": "address"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]

# Proxy creation code used for CREATE2 address derivation (fixed for GnosisSafe v1.3)
_PROXY_CREATION_CODE = bytes.fromhex(
    "608060405234801561001057600080fd5b506040516101e63803806101e68339"
    "8101604081905261002f91610054565b6001600160a01b03811660009081526020"
    "8190526040902060010155610084565b60006020828403121561006657600080fd5b"
    "81516001600160a01b038116811461007d57600080fd5b9392505050565b60e06100"
    "928339019056fe"
)


def _build_setup_data(owner_eoa: str) -> bytes:
    """Build the `initializer` bytes for a 1-of-1 Safe owned by `owner_eoa`."""
    zero = "0x0000000000000000000000000000000000000000"
    args = encode(
        ["address[]", "uint256", "address", "bytes", "address", "address", "uint256", "address"],
        [[Web3.to_checksum_address(owner_eoa)], 1, zero, b"", zero, zero, 0, zero],
    )
    return _SETUP_SELECTOR + args


def compute_safe_address(owner_eoa: str, singleton: str) -> str:
    """Compute the deterministic Safe address for an EOA (no network call).

    Uses CREATE2 with saltNonce = int(owner_eoa, 16) % 2**256.
    """
    settings = get_settings()
    factory = settings.gnosis_safe_proxy_factory

    init_data = _build_setup_data(owner_eoa)
    salt_nonce = int(owner_eoa, 16) % (2**256)

    # Salt = keccak256(keccak256(initializer) ++ saltNonce)
    init_hash = Web3.keccak(init_data)
    salt = Web3.keccak(
        encode(["bytes32", "uint256"], [init_hash, salt_nonce])
    )

    # Proxy creation code hash encodes the singleton address
    proxy_init = _PROXY_CREATION_CODE + encode(["address"], [Web3.to_checksum_address(singleton)])
    proxy_init_hash = Web3.keccak(proxy_init)

    # CREATE2: keccak256(0xff ++ factory ++ salt ++ keccak256(initCode))
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
        self._w3: Optional[Web3] = None

    def _get_w3(self) -> Web3:
        if self._w3 is None:
            self._w3 = Web3(Web3.HTTPProvider(self._settings.polygon_rpc_url))
        return self._w3

    async def deploy_safe(self, owner_eoa: str) -> str:
        """Deploy a 1-of-1 Safe for owner_eoa and return its address.

        If the Safe is already deployed at the computed address, returns
        the address without re-deploying (idempotent).
        """
        import asyncio

        singleton = self._settings.gnosis_safe_singleton
        safe_addr = compute_safe_address(owner_eoa, singleton)

        w3 = self._get_w3()

        # Check if already deployed
        loop = asyncio.get_event_loop()
        code = await loop.run_in_executor(None, lambda: w3.eth.get_code(safe_addr))
        if code and code != b"" and code != b"\x00":
            logger.info("Safe already deployed at %s", safe_addr)
            return safe_addr

        factory = w3.eth.contract(
            address=self._settings.gnosis_safe_proxy_factory,
            abi=_PROXY_FACTORY_ABI,
        )
        deployer_account = Account.from_key(self._settings.builder_private_key)
        init_data = _build_setup_data(owner_eoa)
        salt_nonce = int(owner_eoa, 16) % (2**256)

        nonce = await loop.run_in_executor(
            None, lambda: w3.eth.get_transaction_count(deployer_account.address)
        )
        gas_price = await loop.run_in_executor(None, lambda: w3.eth.gas_price)

        tx = factory.functions.createProxyWithNonce(
            self._settings.gnosis_safe_singleton,
            init_data,
            salt_nonce,
        ).build_transaction({
            "from": deployer_account.address,
            "nonce": nonce,
            "gasPrice": int(gas_price * 1.1),
            "gas": 300_000,
            "chainId": 137,
        })

        signed = deployer_account.sign_transaction(tx)
        tx_hash = await loop.run_in_executor(
            None, lambda: w3.eth.send_raw_transaction(signed.rawTransaction)
        )

        logger.info("Safe deployment tx: %s for owner %s", tx_hash.hex(), owner_eoa)

        # Wait for receipt (up to 60 seconds)
        receipt = await loop.run_in_executor(
            None, lambda: w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        )
        if receipt["status"] != 1:
            raise RuntimeError(f"Safe deployment failed: tx {tx_hash.hex()}")

        logger.info("Safe deployed at %s (owner: %s)", safe_addr, owner_eoa)
        return safe_addr
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_safe_deployer.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/trading/safe_deployer.py tests/unit/test_safe_deployer.py
git commit -m "feat(trading): Safe deployer — deterministic address + deploy via web3"
```

---

## Task 4: Update CLOB client to py-clob-client-v2

**Files:**
- Modify: `app/trading/builder_client.py`

Migrate from v1 (dict-based order args) to v2 (typed dataclasses). Add `get_user_clob_client(safe_address)` factory that sets `funder=safe_address`.

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_clob_client.py`:

```python
"""Tests for the v2 CLOB client wrapper."""
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from app.trading.builder_client import get_user_clob_client, BuilderTradeClient


class TestGetUserClobClient:
    @patch("app.trading.builder_client.ClobClient")
    def test_creates_client_with_funder(self, mock_clob_cls):
        mock_clob_cls.return_value = MagicMock()
        client = get_user_clob_client("0xSafeAddress")
        call_kwargs = mock_clob_cls.call_args.kwargs
        assert call_kwargs["funder"] == "0xSafeAddress"

    @patch("app.trading.builder_client.ClobClient")
    def test_creates_client_with_builder_creds(self, mock_clob_cls):
        mock_clob_cls.return_value = MagicMock()
        get_user_clob_client("0xSafe")
        call_kwargs = mock_clob_cls.call_args.kwargs
        assert call_kwargs["key"] is not None or call_kwargs.get("creds") is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_clob_client.py -v
```

Expected: `ImportError` or `AttributeError` — `get_user_clob_client` not yet defined.

- [ ] **Step 3: Rewrite `app/trading/builder_client.py`**

```python
"""CLOB client — py-clob-client-v2 wrapper for order execution."""

import asyncio
import logging
from functools import partial
from typing import Optional

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    MarketOrderArgs,
    OrderArgs,
    OrderType,
    PartialCreateOrderOptions,
    Side,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)

CLOB_HOST = "https://clob.polymarket.com"


def _build_builder_creds(s) -> Optional[ApiCreds]:
    if s.builder_api_key and s.builder_api_secret and s.builder_api_passphrase:
        return ApiCreds(
            api_key=s.builder_api_key,
            api_secret=s.builder_api_secret,
            api_passphrase=s.builder_api_passphrase,
        )
    return None


def get_user_clob_client(safe_address: str) -> ClobClient:
    """Return a ClobClient that signs with the builder key but funds from user's Safe."""
    s = get_settings()
    if not s.builder_private_key:
        raise RuntimeError("BUILDER_PRIVATE_KEY not configured")
    creds = _build_builder_creds(s)
    client = ClobClient(
        host=CLOB_HOST,
        chain_id=s.polygon_chain_id,
        key=s.builder_private_key,
        creds=creds,
        funder=safe_address,
    )
    if creds is None:
        derived = client.create_or_derive_api_key()
        client.set_api_creds(derived)
    return client


class BuilderTradeClient:
    """Async wrapper around py-clob-client-v2 for a given user Safe."""

    def __init__(self, safe_address: str):
        self._safe_address = safe_address
        self._client: Optional[ClobClient] = None
        self._settings = get_settings()

    def _get_client(self) -> ClobClient:
        if self._client is None:
            self._client = get_user_clob_client(self._safe_address)
        return self._client

    async def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        tick_size: str = "0.01",
        neg_risk: bool = False,
    ) -> dict:
        client = self._get_client()
        order_args = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=Side.BUY if side.upper() == "BUY" else Side.SELL,
            builder_code=self._settings.polymarket_builder_code,
        )
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                partial(client.create_and_post_order, order_args, options, OrderType.GTC),
            )
            order_id = resp.get("orderID") or resp.get("order_id")
            logger.info(
                "Limit order placed: side=%s price=%.4f size=%.1f token=%s → %s",
                side, price, size, token_id[:16], order_id or "?",
            )
            return {
                "success": bool(resp.get("success", False) or order_id),
                "order_id": order_id,
                "error": resp.get("errorMsg"),
            }
        except Exception as e:
            logger.error("Limit order failed: %s", e, exc_info=True)
            return {"success": False, "order_id": None, "error": str(e)}

    async def place_market_order(
        self,
        token_id: str,
        side: str,
        amount: float,
        tick_size: str = "0.01",
        neg_risk: bool = False,
    ) -> dict:
        client = self._get_client()
        order_args = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=Side.BUY if side.upper() == "BUY" else Side.SELL,
            order_type=OrderType.FOK,
            builder_code=self._settings.polymarket_builder_code,
        )
        options = PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk)
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                partial(client.create_and_post_market_order, order_args, options),
            )
            order_id = resp.get("orderID") or resp.get("order_id")
            logger.info(
                "Market order: side=%s amount=%.2f token=%s → %s",
                side, amount, token_id[:16], order_id or "?",
            )
            return {
                "success": bool(resp.get("success", False) or order_id),
                "order_id": order_id,
                "error": resp.get("errorMsg"),
            }
        except Exception as e:
            logger.error("Market order failed: %s", e, exc_info=True)
            return {"success": False, "order_id": None, "error": str(e)}

    async def get_order(self, order_id: str) -> Optional[dict]:
        client = self._get_client()
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, partial(client.get_order, order_id))
        except Exception as e:
            logger.error("get_order %s failed: %s", order_id, e)
            return None

    async def cancel_order(self, order_id: str) -> dict:
        client = self._get_client()
        try:
            resp = client.cancel_order(order_id)
            return {"success": True, "data": resp}
        except Exception as e:
            logger.error("Cancel failed: %s", e, exc_info=True)
            return {"success": False, "error": str(e)}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/unit/test_clob_client.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/trading/builder_client.py tests/unit/test_clob_client.py
git commit -m "feat(trading): migrate CLOB client to py-clob-client-v2, add funder+builder_code"
```

---

## Task 5: Wallet API routes

**Files:**
- Create: `app/api/routes/trading_wallet.py`
- Create: `tests/unit/test_trading_wallet.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/test_trading_wallet.py`:

```python
"""Tests for wallet connect/status endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestWalletStatus:
    def test_requires_auth(self, client):
        resp = client.get("/api/trading/wallet/status")
        assert resp.status_code == 403  # no auth header

    @patch("app.api.routes.trading_wallet.get_current_user")
    def test_returns_not_connected_when_no_safe(self, mock_get_user, client):
        user = MagicMock()
        user.wallet_address = None
        user.polymarket_safe_address = None
        mock_get_user.return_value = user
        resp = client.get(
            "/api/trading/wallet/status",
            headers={"Authorization": "Bearer fake"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["connected"] is False
        assert data["safe_address"] is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/unit/test_trading_wallet.py::TestWalletStatus::test_requires_auth -v
```

Expected: FAIL or error (route doesn't exist yet).

- [ ] **Step 3: Create `app/api/routes/trading_wallet.py`**

```python
"""Wallet connection endpoints — EOA registration + Safe deployment."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.db.database import get_db_session
from app.db.models import UserProfile
from app.trading.safe_deployer import SafeDeployer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading/wallet", tags=["trading-wallet"])

_deployer = SafeDeployer()


class ConnectRequest(BaseModel):
    eoa_address: str


class WalletStatusResponse(BaseModel):
    connected: bool
    eoa_address: str | None
    safe_address: str | None


class ConnectResponse(BaseModel):
    safe_address: str


@router.get("/status", response_model=WalletStatusResponse)
async def wallet_status(
    user: UserProfile = Depends(get_current_user),
):
    """Return the user's wallet connection status."""
    return WalletStatusResponse(
        connected=bool(user.polymarket_safe_address),
        eoa_address=user.wallet_address,
        safe_address=user.polymarket_safe_address,
    )


@router.post("/connect", response_model=ConnectResponse)
async def connect_wallet(
    body: ConnectRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Register user's EOA and deploy (or retrieve) their Gnosis Safe."""
    eoa = body.eoa_address.strip().lower()
    if not eoa.startswith("0x") or len(eoa) != 42:
        raise HTTPException(status_code=400, detail="Invalid EOA address")

    # Return early if Safe already deployed
    if user.polymarket_safe_address:
        return ConnectResponse(safe_address=user.polymarket_safe_address)

    try:
        safe_address = await _deployer.deploy_safe(eoa)
    except Exception as e:
        logger.error("Safe deployment failed for %s: %s", eoa, e)
        raise HTTPException(status_code=500, detail=f"Safe deployment failed: {e}")

    user.wallet_address = eoa
    user.polymarket_safe_address = safe_address
    await db.commit()

    logger.info("Wallet connected: user=%d eoa=%s safe=%s", user.id, eoa, safe_address)
    return ConnectResponse(safe_address=safe_address)
```

- [ ] **Step 4: Register router in `app/api/main.py`**

After the existing `from app.api.routes.trading import router as trading_router` line, add:

```python
from app.api.routes.trading_wallet import router as trading_wallet_router  # noqa: E402
```

After `app.include_router(trading_router, prefix="/api")`, add:

```python
app.include_router(trading_wallet_router, prefix="/api")
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/unit/test_trading_wallet.py -v
```

Expected: `test_requires_auth` PASS (403 because no auth token), `test_returns_not_connected_when_no_safe` may need adjustment based on how mock_get_user interacts with the dependency override — if it fails due to dependency wiring, use `app.dependency_overrides`:

```python
# Alternative if mock doesn't work via patch:
from app.api.routes.auth import get_current_user
app.dependency_overrides[get_current_user] = lambda: user
```

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/trading_wallet.py app/api/main.py tests/unit/test_trading_wallet.py
git commit -m "feat(api): add /trading/wallet/status and /trading/wallet/connect endpoints"
```

---

## Task 6: Update trading route to use per-user client

**Files:**
- Modify: `app/api/routes/trading.py`

Add auth dependency and switch from `get_trade_client()` (shared builder) to `BuilderTradeClient(safe_address)` (per-user).

- [ ] **Step 1: Update `app/api/routes/trading.py`**

At the top of the file, add the import:

```python
from app.api.routes.auth import get_current_user
```

Replace the `place_trade` function signature from:

```python
@router.post("/trade", response_model=TradeResponse)
async def place_trade(
    req: TradeRequest,
    db: AsyncSession = Depends(get_db_session),
):
```

To:

```python
@router.post("/trade", response_model=TradeResponse)
async def place_trade(
    req: TradeRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
```

At the beginning of the function body, add the wallet guard before the market lookup:

```python
    if not user.polymarket_safe_address:
        return TradeResponse(
            success=False,
            error="wallet_not_connected",
        )
```

Replace the `from app.trading.builder_client import get_trade_client` block and the `client = get_trade_client()` line with:

```python
    from app.trading.builder_client import BuilderTradeClient
    client = BuilderTradeClient(user.polymarket_safe_address)
```

Remove the `portfolio = await _get_or_create_portfolio(db)` call and update `Order` creation to use `user.id` instead of `portfolio.id`:

The full updated function body:

```python
    if not user.polymarket_safe_address:
        return TradeResponse(success=False, error="wallet_not_connected")

    market_result = await db.execute(select(Market).where(Market.market_id == req.market_id))
    market = market_result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    if not market.clob_token_ids:
        raise HTTPException(status_code=400, detail="Market has no token IDs for trading")

    token_ids = market.clob_token_ids
    if req.direction == "BUY_YES":
        token_id = token_ids.get("yes") or token_ids.get("YES")
        side = "BUY"
    elif req.direction == "BUY_NO":
        token_id = token_ids.get("no") or token_ids.get("NO")
        side = "BUY"
    else:
        raise HTTPException(status_code=400, detail="direction must be BUY_YES or BUY_NO")

    if not token_id:
        raise HTTPException(status_code=400, detail="Could not resolve token ID for direction")

    price = req.price or float(market.last_trade_price or 0.5)

    from app.trading.builder_client import BuilderTradeClient
    client = BuilderTradeClient(user.polymarket_safe_address)

    try:
        if req.price:
            resp = await client.place_limit_order(
                token_id=token_id, side=side, price=price, size=req.amount,
            )
        else:
            resp = await client.place_market_order(
                token_id=token_id, side=side, amount=req.amount,
            )

        success = resp.get("success", False)
        return TradeResponse(
            success=success,
            polymarket_order_id=resp.get("order_id"),
            error=resp.get("error") if not success else None,
        )

    except Exception as e:
        logger.error("Trade execution error: %s", e, exc_info=True)
        return TradeResponse(success=False, error=str(e))
```

Note: This removes the `Order` DB model persistence to simplify the flow. Order tracking is handled by Polymarket's CLOB. Re-add it later if needed.

- [ ] **Step 2: Verify no import errors**

```bash
cd /Users/vadim/polymarket-ai
python -c "from app.api.routes.trading import router; print('trading route ok')"
```

Expected: `trading route ok`

- [ ] **Step 3: Commit**

```bash
git add app/api/routes/trading.py
git commit -m "feat(trading): per-user Safe execution — add auth, use BuilderTradeClient(safe_addr)"
```

---

## Task 7: Frontend deps + WagmiProvider

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Install wagmi + viem**

```bash
cd /Users/vadim/polymarket-ai/frontend
npm install wagmi@2 viem@2 @wagmi/connectors@5
```

Expected: packages installed, no peer dep errors (React 18 is compatible).

- [ ] **Step 2: Create wagmi config `frontend/src/lib/wagmiConfig.ts`**

```typescript
import { createConfig, http } from "wagmi"
import { polygon } from "wagmi/chains"
import { injected, walletConnect } from "wagmi/connectors"

const projectId = import.meta.env.VITE_WALLETCONNECT_PROJECT_ID as string | undefined

const connectors = projectId
  ? [injected(), walletConnect({ projectId })]
  : [injected()]

export const wagmiConfig = createConfig({
  chains: [polygon],
  connectors,
  transports: {
    [polygon.id]: http(),
  },
})
```

- [ ] **Step 3: Wrap app in `WagmiProvider` in `frontend/src/main.tsx`**

Open `frontend/src/main.tsx`. Add imports at the top:

```typescript
import { WagmiProvider } from "wagmi"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { wagmiConfig } from "@/lib/wagmiConfig"
```

Install `@tanstack/react-query` (wagmi peer dep):

```bash
cd /Users/vadim/polymarket-ai/frontend
npm install @tanstack/react-query
```

Wrap the `<App />` render:

```tsx
const queryClient = new QueryClient()

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <WagmiProvider config={wagmiConfig}>
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>
    </WagmiProvider>
  </StrictMode>,
)
```

- [ ] **Step 4: Verify build**

```bash
cd /Users/vadim/polymarket-ai/frontend
npm run build 2>&1 | tail -20
```

Expected: build completes without errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/lib/wagmiConfig.ts
git commit -m "feat(frontend): add wagmi v2 + WagmiProvider, polygon chain config"
```

---

## Task 8: Wallet API client

**Files:**
- Create: `frontend/src/lib/api/wallet.ts`

- [ ] **Step 1: Create `frontend/src/lib/api/wallet.ts`**

```typescript
/**
 * Wallet connection API — EOA registration + Safe deployment.
 */
import { apiGet, apiPost } from "@/lib/api/client"

export type WalletStatus = {
  connected: boolean
  eoa_address: string | null
  safe_address: string | null
}

export type ConnectResponse = {
  safe_address: string
}

export async function getWalletStatus(): Promise<WalletStatus> {
  return apiGet<WalletStatus>("/trading/wallet/status")
}

export async function connectWallet(eoa_address: string): Promise<ConnectResponse> {
  return apiPost<ConnectResponse>("/trading/wallet/connect", { eoa_address })
}
```

- [ ] **Step 2: Verify types compile**

```bash
cd /Users/vadim/polymarket-ai/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to `wallet.ts`.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add frontend/src/lib/api/wallet.ts
git commit -m "feat(frontend): add wallet API client (getWalletStatus, connectWallet)"
```

---

## Task 9: useWalletSetup hook

**Files:**
- Create: `frontend/src/hooks/useWalletSetup.ts`

- [ ] **Step 1: Create `frontend/src/hooks/useWalletSetup.ts`**

```typescript
import { useCallback, useEffect, useState } from "react"
import { useAccount, useConnect, useDisconnect } from "wagmi"
import { injected } from "wagmi/connectors"
import { getWalletStatus, connectWallet, type WalletStatus } from "@/lib/api/wallet"
import { hasToken } from "@/lib/api/auth"

type SetupStep = "idle" | "connecting_wallet" | "deploying_safe" | "done" | "error"

type UseWalletSetupReturn = {
  /** Whether the user has a deployed Safe linked to their account. */
  walletConnected: boolean
  safeAddress: string | null
  eoaAddress: string | null
  step: SetupStep
  error: string | null
  /** Start the full wallet connect + Safe deploy flow. */
  startSetup: () => Promise<void>
  /** Refetch status from backend (call after login). */
  refreshStatus: () => Promise<void>
}

export function useWalletSetup(): UseWalletSetupReturn {
  const [status, setStatus] = useState<WalletStatus>({
    connected: false,
    eoa_address: null,
    safe_address: null,
  })
  const [step, setStep] = useState<SetupStep>("idle")
  const [error, setError] = useState<string | null>(null)

  const { address: connectedAddress } = useAccount()
  const { connectAsync } = useConnect()

  const refreshStatus = useCallback(async () => {
    if (!hasToken()) return
    try {
      const s = await getWalletStatus()
      setStatus(s)
      if (s.connected) setStep("done")
    } catch {
      // silently ignore — user may not be authed
    }
  }, [])

  useEffect(() => {
    refreshStatus()
  }, [refreshStatus])

  const startSetup = useCallback(async () => {
    setError(null)
    try {
      // Step 1: connect MetaMask
      setStep("connecting_wallet")
      let eoa = connectedAddress
      if (!eoa) {
        const result = await connectAsync({ connector: injected() })
        eoa = result.accounts[0]
      }
      if (!eoa) throw new Error("Wallet connection refused")

      // Step 2: deploy Safe on backend
      setStep("deploying_safe")
      const resp = await connectWallet(eoa.toLowerCase())

      setStatus({ connected: true, eoa_address: eoa, safe_address: resp.safe_address })
      setStep("done")
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      setError(msg)
      setStep("error")
    }
  }, [connectedAddress, connectAsync])

  return {
    walletConnected: status.connected,
    safeAddress: status.safe_address,
    eoaAddress: status.eoa_address,
    step,
    error,
    startSetup,
    refreshStatus,
  }
}
```

- [ ] **Step 2: Verify types**

```bash
cd /Users/vadim/polymarket-ai/frontend
npx tsc --noEmit 2>&1 | grep "useWalletSetup" | head -10
```

Expected: no errors for `useWalletSetup.ts`.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add frontend/src/hooks/useWalletSetup.ts
git commit -m "feat(frontend): useWalletSetup hook — MetaMask connect + Safe deploy flow"
```

---

## Task 10: WalletSetupModal component

**Files:**
- Create: `frontend/src/components/trading/WalletSetupModal.tsx`

- [ ] **Step 1: Create `frontend/src/components/trading/WalletSetupModal.tsx`**

```tsx
import { useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { CheckCircle, Loader2, Wallet, X } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { useWalletSetup } from "@/hooks/useWalletSetup"
import { cn } from "@/lib/utils"

type Props = {
  open: boolean
  /** Called when the Safe is successfully deployed and ready for trading. */
  onSuccess: () => void
  /** Called when the user dismisses the modal without completing. */
  onClose: () => void
}

const STEP_LABELS = {
  idle: null,
  connecting_wallet: "Connexion à MetaMask…",
  deploying_safe: "Déploiement de ton Safe Polymarket…",
  done: "Prêt à trader !",
  error: null,
}

export function WalletSetupModal({ open, onSuccess, onClose }: Props) {
  const { step, error, startSetup, walletConnected } = useWalletSetup()

  useEffect(() => {
    if (step === "done") {
      const t = setTimeout(onSuccess, 800)
      return () => clearTimeout(t)
    }
  }, [step, onSuccess])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 8 }}
            transition={{ duration: 0.15 }}
            className="relative w-full max-w-sm rounded-2xl border border-line-strong bg-obsidian-900 p-6 shadow-2xl"
          >
            <button
              onClick={onClose}
              className="absolute right-4 top-4 rounded-md p-1 text-ink-dim hover:text-ink transition-premium"
              aria-label="Fermer"
            >
              <X className="h-4 w-4" />
            </button>

            {/* Icon */}
            <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-brand-500/40 bg-brand-500/10">
              {step === "done" ? (
                <CheckCircle className="h-6 w-6 text-signal-yes" />
              ) : (
                <Wallet className="h-6 w-6 text-brand-400" />
              )}
            </div>

            <h2 className="mb-1 font-display text-title-sm font-semibold text-ink">
              {step === "done" ? "Wallet connecté !" : "Active le trading natif"}
            </h2>
            <p className="mb-5 text-body-sm text-ink-muted">
              {step === "done"
                ? "Ton Safe Polymarket est prêt. Dépose des USDC pour commencer."
                : "Connecte ton wallet MetaMask une seule fois. Tous tes ordres suivants seront exécutés automatiquement."}
            </p>

            {/* Steps progress */}
            <ol className="mb-5 space-y-2">
              {[
                { id: "connecting_wallet", label: "Connecte ton wallet (MetaMask)" },
                { id: "deploying_safe", label: "Déploiement de ton Safe Polymarket" },
                { id: "done", label: "Dépose des USDC dans ton Safe" },
              ].map(({ id, label }) => {
                const stepOrder = ["idle", "connecting_wallet", "deploying_safe", "done", "error"]
                const currentIdx = stepOrder.indexOf(step)
                const thisIdx = stepOrder.indexOf(id)
                const isActive = step === id
                const isDone = currentIdx > thisIdx

                return (
                  <li
                    key={id}
                    className={cn(
                      "flex items-center gap-2.5 text-body-sm",
                      isDone ? "text-signal-yes" : isActive ? "text-ink" : "text-ink-dim",
                    )}
                  >
                    {isDone ? (
                      <CheckCircle className="h-4 w-4 shrink-0 text-signal-yes" />
                    ) : isActive ? (
                      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-400" />
                    ) : (
                      <span className="h-4 w-4 shrink-0 rounded-full border border-line-strong" />
                    )}
                    {label}
                  </li>
                )
              })}
            </ol>

            {error && (
              <p className="mb-4 rounded-md border border-signal-no/40 bg-signal-no/10 px-3 py-2 text-body-sm text-signal-no">
                {error}
              </p>
            )}

            {step === "done" ? (
              <Button variant="primary" size="lg" className="w-full" onClick={onSuccess}>
                Continuer vers le portfolio
              </Button>
            ) : (
              <Button
                variant="primary"
                size="lg"
                className="w-full"
                onClick={startSetup}
                disabled={step === "connecting_wallet" || step === "deploying_safe"}
              >
                {step === "connecting_wallet" || step === "deploying_safe" ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {STEP_LABELS[step]}
                  </>
                ) : (
                  <>
                    <Wallet className="h-4 w-4" />
                    Connecter MetaMask
                  </>
                )}
              </Button>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd /Users/vadim/polymarket-ai/frontend
npx tsc --noEmit 2>&1 | grep "WalletSetupModal" | head -10
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add frontend/src/components/trading/WalletSetupModal.tsx
git commit -m "feat(frontend): WalletSetupModal — 3-step wallet connect + Safe deploy UI"
```

---

## Task 11: Wire OrderForm to wallet setup

**Files:**
- Modify: `frontend/src/components/signals/OrderForm.tsx`

Gate form submission on `walletConnected`. If not connected, show `WalletSetupModal` instead.

- [ ] **Step 1: Add wallet setup gate to `OrderForm.tsx`**

At the top of the `OrderForm` function body, add these hooks after the existing hook declarations (around line 77):

```tsx
  const { walletConnected, startSetup } = useWalletSetup()
  const [showWalletModal, setShowWalletModal] = useState(false)
```

Add the imports at the top of the file:

```tsx
import { useWalletSetup } from "@/hooks/useWalletSetup"
import { WalletSetupModal } from "@/components/trading/WalletSetupModal"
```

In `handleSubmit`, before the `setSubmitted(true)` line, add the wallet gate:

```tsx
    // Wallet gate: require Safe before placing any order
    if (!walletConnected) {
      setShowWalletModal(true)
      return
    }
```

At the end of the returned JSX, just before the closing `</motion.form>`, add the modal:

```tsx
      <WalletSetupModal
        open={showWalletModal}
        onSuccess={() => setShowWalletModal(false)}
        onClose={() => setShowWalletModal(false)}
      />
```

- [ ] **Step 2: Full build check**

```bash
cd /Users/vadim/polymarket-ai/frontend
npm run build 2>&1 | tail -30
```

Expected: build completes with no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
cd /Users/vadim/polymarket-ai
git add frontend/src/components/signals/OrderForm.tsx
git commit -m "feat(frontend): gate OrderForm on wallet setup — show WalletSetupModal if not connected"
```

---

## Task 12: End-to-end smoke test

- [ ] **Step 1: Start the backend**

```bash
cd /Users/vadim/polymarket-ai
uvicorn app.api.main:app --reload --port 8000
```

- [ ] **Step 2: Verify wallet endpoints exist**

```bash
curl -s http://localhost:8000/api/trading/wallet/status \
  -H "Authorization: Bearer invalid_token" | python3 -m json.tool
```

Expected: `{"detail": "Invalid or expired token"}` (401) — proves the route is registered and auth is working.

- [ ] **Step 3: Verify trade endpoint requires wallet**

Login to get a valid JWT, then:

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -X POST http://localhost:8000/api/trading/trade \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"market_id":"test","direction":"BUY_YES","amount":10}' | python3 -m json.tool
```

Expected: `{"success": false, "error": "wallet_not_connected"}` (200 with error field) — proves auth works and wallet guard triggers.

- [ ] **Step 4: Start the frontend**

```bash
cd /Users/vadim/polymarket-ai/frontend
npm run dev
```

Navigate to a signal detail page. Click "Investir". Confirm `WalletSetupModal` appears with "Connecter MetaMask" button.

- [ ] **Step 5: Final commit**

```bash
cd /Users/vadim/polymarket-ai
git add .
git commit -m "feat: Polymarket per-user wallet trading — Safe deploy + zero-friction orders"
```

---

## Self-Review

**Spec coverage:**
- ✅ `ClobClient(funder=user_safe)` pattern — Task 4
- ✅ `builder_code` on every order — Task 4 (`BuilderTradeClient.place_limit_order/market_order`)
- ✅ One-time wallet connect (MetaMask) — Tasks 9, 10
- ✅ Backend Safe deployment via web3.py — Task 3
- ✅ `polymarket_safe_address` DB column — Task 2
- ✅ Wallet status + connect API routes — Task 5
- ✅ Auth required on `/api/trading/trade` — Task 6
- ✅ WagmiProvider in main.tsx — Task 7
- ✅ `wallet_not_connected` guard in trade endpoint — Task 6
- ✅ OrderForm gate on wallet setup — Task 11

**Out of scope (confirmed):**
- Turnkey, USDC onramp, credential revocation, Safe multi-sig
