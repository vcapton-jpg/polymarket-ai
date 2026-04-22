# Design — Polymarket Wallet Link (Link Once, Trade Forever)

**Date:** 2026-04-22  
**Status:** Approved  

---

## Problem

The current `/api/trading/trade` endpoint uses a single builder wallet (`BuilderTradeClient`) to place all orders. This is wrong: the builder's private key signs every order, which means Foresight's USDC would fund all trades. Orders should come from each user's own wallet.

The builder credentials exist only for **attribution** — attaching `builderCode` to every order so Polymarket credits volume to Foresight's builder account. They must never be used to fund user trades.

---

## Goal

A Foresight user clicks "Investir" and an order lands on Polymarket using their own USDC. After a one-time 10-second wallet-link step, subsequent trades require zero wallet interaction — one click, done.

---

## Architecture

### Concept: One-time credential derivation

Polymarket's CLOB API uses credentials (`api_key`, `api_secret`, `api_passphrase`) derived deterministically from a wallet's private key via an EIP-712 signature. Once derived and stored server-side (encrypted), the backend can place orders on the user's behalf without any further wallet interaction.

```
One-time (first trade only):
  User → MetaMask → sign EIP-712 message
      → frontend derives CLOB creds
      → POST /api/trading/wallet/link {eoa, api_key, api_secret, api_passphrase}
      → stored encrypted in UserProfile

Every subsequent trade:
  User clicks "Investir"
      → POST /api/trading/trade {market_id, direction, amount, price}
      → backend fetches user's CLOB creds from DB
      → py-clob-client places order with builderCode attached
      → order confirmed
```

### What the user owns

The user's USDC stays in their Polygon wallet. Foresight never takes custody. The stored credentials give Foresight permission to place CLOB orders (not withdraw funds). Users can revoke by re-deriving new credentials on Polymarket.

---

## Backend Changes

### 1. Database — `UserProfile` model (`app/db/models.py`)

Add 4 encrypted fields:
- `polymarket_eoa: str` — user's Polygon address
- `polymarket_api_key: str` — encrypted CLOB api_key
- `polymarket_api_secret: str` — encrypted CLOB api_secret  
- `polymarket_api_passphrase: str` — encrypted CLOB api_passphrase

Encryption: Fernet symmetric encryption using `FORESIGHT_ENCRYPTION_KEY` env var. Encrypt on write, decrypt on read inside the service layer.

### 2. New route — `app/api/routes/trading_wallet.py`

`POST /api/trading/wallet/link`  
Auth required. Body: `{eoa_address, api_key, api_secret, api_passphrase}`.  
Encrypts and stores creds on the current user's `UserProfile`. Returns `{linked: true}`.

`GET /api/trading/wallet/status`  
Returns `{linked: bool, eoa_address: str | null}`. Used by the frontend to decide whether to show the wallet-link modal.

### 3. Update trading route — `app/api/routes/trading.py`

`POST /api/trading/trade`: replace `get_trade_client()` with a per-user client:
- Fetch authenticated user's CLOB creds from `UserProfile`
- If no creds: return `{success: false, error: "wallet_not_linked"}`
- Build `ClobClient` with user's creds (using `py-clob-client` `ApiCreds`)
- Attach `builderCode` in `order_args` on every order

### 4. Config — `app/core/config.py`

Add:
- `foresight_encryption_key: str` — Fernet key for credential encryption
- `polymarket_builder_code: str` — builder code from polymarket.com/settings?tab=builder (already have `builder_private_key` etc., add the attribution code)

---

## Frontend Changes

### 1. New hook — `src/hooks/useWalletLink.ts`

Manages wallet link state:
- `GET /api/trading/wallet/status` on mount → `{linked, eoa}`
- `linkWallet()`: triggers wagmi wallet connection → EIP-712 sign → derives CLOB creds (using `@polymarket/clob-client` JS or manual EIP-712 derivation) → `POST /api/trading/wallet/link`

### 2. New component — `src/components/trading/WalletLinkModal.tsx`

Shown when user tries to trade but has no linked wallet:
- "Connecte ton wallet Polymarket" heading
- Connect button (wagmi `useConnect` — MetaMask + WalletConnect)
- One-click sign + link flow
- On success: dismisses, order proceeds

### 3. Update `OrderForm.tsx`

Before submit: check `walletLinked` from `useWalletLink`. If false → open `WalletLinkModal` instead of submitting. On link success → resubmit.

### 4. New dependencies — `frontend/package.json`

- `wagmi` — wallet connection + EIP-712 signing
- `viem` — low-level EVM types, used by wagmi
- `@wagmi/connectors` — MetaMask + WalletConnect connectors

---

## CLOB Credential Derivation (EIP-712)

Polymarket's CLOB API key derivation is a standard EIP-712 sign of a specific message. The `py-clob-client` method `ClobClient.derive_api_key()` returns `{api_key, api_secret, api_passphrase}` when given the wallet's private key.

On the frontend, we replicate this by having the user sign the same EIP-712 message via MetaMask, then reconstruct the credentials. The `@polymarket/clob-client` JS package exposes `deriveApiKey(signer)` for this.

The derived creds are sent to the backend (over HTTPS) immediately after signing — they are never stored in localStorage.

---

## Builder Code Attribution

In `builder_client.py`, every `order_args` dict gets `builderCode` injected:

```python
order_args = {
    "token_id": token_id,
    "price": price,
    "size": size,
    "side": side.upper(),
    "builderCode": settings.polymarket_builder_code,  # ← new
}
```

This is the only change needed for volume attribution. No other builder-credential usage is required.

---

## Security

- CLOB credentials stored with Fernet encryption (symmetric AES-128-CBC + HMAC). Key stored in env, never in DB.
- Credentials transmitted only over HTTPS.
- Credentials give CLOB order-placement access, not fund withdrawal.
- `GET /api/trading/wallet/status` returns only `eoa_address` (public), never credentials.

---

## Migration

1. Alembic migration: add 4 nullable columns to `user_profiles`
2. New env var: `FORESIGHT_ENCRYPTION_KEY` (generate with `Fernet.generate_key()`)
3. New env var: `POLYMARKET_BUILDER_CODE` (copy from polymarket.com/settings?tab=builder)
4. Frontend: add wagmi deps + WagmiProvider wrapper in `main.tsx`

---

## Out of Scope

- Gnosis Safe deployment (not needed — user's EOA works directly with CLOB)
- Turnkey wallet provisioning (future enhancement for new-to-crypto users)
- USDC deposit flow (users manage their own Polygon USDC)
- Credential revocation UI (users can re-derive on polymarket.com)
