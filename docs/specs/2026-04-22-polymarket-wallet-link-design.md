# Design — Polymarket Per-User Trading (Link Once, Trade Forever)

**Date:** 2026-04-22  
**Status:** Approved (revised after py-clob-client-v2 review)

---

## Problem

The current `/api/trading/trade` endpoint uses a single builder wallet (`BuilderTradeClient`) to sign all orders. This means Foresight's USDC funds every trade — wrong. Orders must come from each user's own funds.

Builder credentials exist only for **attribution** — attaching `builder_code` to every `OrderArgsV2` so Polymarket credits volume to Foresight's builder account. They are not a source of funds.

---

## Key insight from py-clob-client-v2

`ClobClient` has a `funder` parameter:

```python
ClobClient(
    host=CLOB_HOST,
    chain_id=137,
    key=builder_private_key,   # Foresight signs
    creds=builder_creds,        # HMAC auth
    funder=user_safe_address,   # USDC comes from user's Safe
)
```

`OrderArgsV2` has a native `builder_code` field (defaults to `BYTES32_ZERO`):

```python
OrderArgsV2(
    token_id=token_id,
    price=price,
    size=size,
    side=Side.BUY,
    builder_code=settings.polymarket_builder_code,
)
```

This means: **the builder key signs every order, but the user's Safe provides the USDC**. After one-time Safe setup, every subsequent trade is zero-friction for the user.

---

## User Flow

### One-time setup (first trade ever)
1. "Activer le trading" → modal wallet connect (MetaMask / WalletConnect)
2. User approves wallet connection (wagmi)
3. Backend deploys a Gnosis Safe for the user → stores `safe_address` in DB
4. Frontend shows user their Safe address + instructs them to deposit USDC
5. Setup complete — Safe address saved, never repeated

### Every trade after setup
1. User clicks "Investir" on a signal
2. `POST /api/trading/trade` with `{market_id, direction, amount, price}`
3. Backend fetches `user.safe_address`, builds `ClobClient(key=builder_pk, funder=safe_addr)`
4. Order placed with `builder_code` attached — user's USDC used, zero wallet interaction

---

## Backend Changes

### 1. Database — `UserProfile` (`app/db/models.py`)

Add two fields:
- `polymarket_eoa: Optional[str]` — user's connected wallet address
- `polymarket_safe_address: Optional[str]` — deployed Gnosis Safe address

### 2. New service — `app/trading/safe_deployer.py`

Deploys a minimal Gnosis Safe proxy for a user address using `web3.py`:
- Calls `GnosisSafeProxyFactory.createProxyWithNonce(masterCopy, setupData, saltNonce)` on Polygon
- `masterCopy` = Gnosis Safe singleton on Polygon (known constant address)
- `setupData` = ABI-encoded `setup([user_eoa], threshold=1, ...)` — user is the Safe owner
- `saltNonce` = `int(user_eoa, 16)` for deterministic address
- Builder wallet pays gas (~$0.001 on Polygon)
- Returns the deployed Safe address (or pre-computes it deterministically before deploying)

### 3. New route — `app/api/routes/trading_wallet.py`

`POST /api/trading/wallet/connect`  
Auth required. Body: `{eoa_address}`.  
Deploys Safe for user (or returns existing one), stores both addresses. Returns `{safe_address}`.

`GET /api/trading/wallet/status`  
Returns `{connected: bool, eoa_address: str|null, safe_address: str|null}`.

### 4. Update `app/trading/builder_client.py` → `app/trading/clob_client.py`

Replace `py_clob_client` (v1) with `py_clob_client_v2`. Key changes:
- `OrderArgs` → typed `OrderArgsV2` dataclass
- `order_args` dict → `OrderArgsV2(token_id=..., price=..., size=..., side=Side.BUY, builder_code=settings.polymarket_builder_code)`
- `MarketOrderArgs` → `MarketOrderArgsV2`
- `PartialCreateOrderOptions` for tick_size
- New `get_user_client(safe_address)` factory: `ClobClient(key=builder_pk, funder=safe_address, creds=builder_creds)`

### 5. Update `app/api/routes/trading.py`

`POST /api/trading/trade`:
- Check `user.polymarket_safe_address` — if None, return `{success: false, error: "wallet_not_connected"}`
- Call `get_user_client(user.safe_address)` instead of `get_trade_client()`
- Rest of logic unchanged

### 6. Config — `app/core/config.py`

Add:
- `polymarket_builder_code: str` — hex bytes32 from polymarket.com/settings?tab=builder
- `polygon_rpc_url: str` — Polygon mainnet RPC (Alchemy/Infura)
- `gnosis_safe_proxy_factory: str` — factory contract address on Polygon
- `gnosis_safe_singleton: str` — Safe master copy address on Polygon

---

## Frontend Changes

### 1. New hook — `src/hooks/useWalletSetup.ts`

- `GET /api/trading/wallet/status` on mount → `{connected, eoa, safe_address}`
- `connectWallet()`: wagmi `connect()` → get account address → `POST /api/trading/wallet/connect {eoa_address}` → receives `safe_address`

### 2. New component — `src/components/trading/WalletSetupModal.tsx`

Shown on first trade attempt when wallet not connected:
- Step 1: "Connecte ton wallet" → MetaMask/WalletConnect button (wagmi `useConnect`)
- Step 2: "Déploiement de ton Safe Polymarket…" (spinner while backend deploys)
- Step 3: "Dépose des USDC" — shows Safe address + copy button + link to Polygon bridge
- Done: dismisses, order proceeds

### 3. Update `OrderForm.tsx`

Before submit: check `walletConnected` from `useWalletSetup`. If false → open `WalletSetupModal`. On setup complete → resubmit.

### 4. New dependencies — `frontend/package.json`

- `wagmi` — wallet connection
- `viem` — EVM types (peer dep of wagmi)
- `@wagmi/connectors` — MetaMask + WalletConnect connectors

---

## Dependencies

### Backend (`pyproject.toml`)
- `py_clob_client_v2` — replaces `py_clob_client`
- `web3>=6.0` — for Safe deployment on Polygon

### Frontend (`package.json`)
- `wagmi` ~2.x
- `viem` ~2.x

---

## Gnosis Safe Contract Addresses (Polygon Mainnet)

- `GnosisSafeProxyFactory`: `0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2`
- `GnosisSafe` singleton: `0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552`

---

## Migration

1. Alembic: add `polymarket_eoa`, `polymarket_safe_address` nullable columns to `user_profiles`
2. New env vars: `POLYGON_RPC_URL`, `POLYMARKET_BUILDER_CODE`
3. Frontend: add wagmi + viem deps, wrap `main.tsx` in `WagmiProvider`
4. Replace `py_clob_client` with `py_clob_client_v2` in `pyproject.toml`

---

## Out of Scope

- Turnkey wallet provisioning (future: removes MetaMask requirement)
- USDC onramp (users bridge their own USDC to Polygon)
- Credential revocation UI
- Safe multi-sig (threshold=1 for simplicity, upgradeable later)
