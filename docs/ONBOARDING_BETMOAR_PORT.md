# Onboarding port — betmoar.fun model → Foresight

Status as of 2026-05-19. Source of truth for the wallet-onboarding
roadmap. betmoar.fun is a fellow Polymarket Builder Program site whose
onboarding is the UX gold standard for our exact target (Polymarket
traders).

## The 4 phases

| Phase | What | Status |
|---|---|---|
| **P1** | Polymarket-tip deposit (counterfactual addr + on-chain confirm) | ✅ **SHIPPED** (PR #121/#123) — derivation **fixed** 2026-05-19 |
| **P2** | Gasless Safe deploy via Polymarket relayer | 🟡 **P2a backend + operator self-test SHIPPED** (gated off); P2b frontend user-sign next |
| **P3** | Bridge (any token/chain → USDC.e) | 🟢 **first-party** `bridge.polymarket.com` (not a 3rd-party widget) |
| **P4** | API-key trading (no per-order signature) | 🟡 buildable; depends on P2 at runtime |

The "blocked on external docs" status was wrong: Polymarket's relayer
+ bridge + CLOB protocols are all in **public, MIT-licensed SDKs**
(`Polymarket/builder-relayer-client`, `Polymarket/py-builder-relayer-client`,
`Polymarket/clob-client`). We can build P2–P4 from a real spec, not
guesswork. Enablement for real money is still gated on the H+72 edge
verdict + one live-RPC verification (below) — that's rigor, not a
blocker.

## 🚨 Critical fix log — 2026-05-19 (Safe address derivation)

**The shipped P1 `compute_safe_address` was deriving the WRONG
address.** It used the stock Gnosis `SafeProxyFactory` +
`saltNonce = int(eoa,16) % 2**256`. Polymarket's relayer uses its OWN
factory and a different salt. A user tipping the old address would
have sent funds to an address Polymarket's relayer never deploys →
**stranded funds**. Risk was ~nil in practice (no real deposits — the
56 accounts are operator-created test accounts) but it had to be fixed
before any real user.

**Corrected derivation** (now in `app/trading/safe_deployer.py`,
pinned by `tests/unit/test_safe_deployer.py`):

```
safe = CREATE2(
    from         = 0xaacFeEa03eb1561C4e67d661e40682Bd20E3541b,   # Polymarket Safe Proxy Factory (Polygon)
    salt         = keccak256(abi.encode(address(owner))),         # 20-byte addr left-padded to 32, then keccak
    initCodeHash = 0x2bce2127ff07fb632d16c8347c4ebf501f4841168bed00d9e6ef715ddb6fcecf,
)[-20:]
```

Source: `Polymarket/builder-relayer-client` `src/builder/derive.ts`
(`deriveSafe`). **Verified byte-for-byte** against Polymarket's own
SDK test fixture (`py-builder-relayer-client`
`tests/builder/test_derive.py::test_derive_safe`): owner
`0x6e0c80c90ea6c15917308F820Eac91Ce2724B5b5` →
`0x6d8c4e9aDF5748Af82Dabe2C6225207770d6B4fa` (intermediate salt
`0xd9d34def…` also matches). The old builder-key `deploy_safe()` path
deployed an incompatible stock-Gnosis Safe; it has been removed and
`deploy_safe()` now raises until the relayer (P2) lands.

### ⚠️ Two Polymarket wallet systems — do not conflate

Confirmed via Polygonscan contract labels:

| Factory | Label | Login type | Derivation |
|---|---|---|---|
| `0xaacFeEa0…20E3541b` | **Safe Proxy Factory** | browser wallet (MetaMask/Rainbow/Coinbase) | `deriveSafe` — `abi.encode` (padded) salt, `SAFE_INIT_CODE_HASH 0x2bce…` |
| `0xaB45c5A4…1A254052` | **Proxy Wallet Factory** | Magic / email | `deriveProxyWallet` — `encodePacked` (unpadded) salt, `PROXY_INIT_CODE_HASH 0xd21df8dc…` |

We sign in via wagmi `useAccount` (browser wallet) → the **Safe** path
is correct. **If email/Magic login is ever added the derivation MUST
branch** — sending USDC.e to a `deriveSafe` address for a Magic user
mis-routes funds. `SafeMultisend = 0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761`
(used only for batched-tx encoding, not derivation).

### Pre-mainnet verification gate (one-time, before real funds at scale)

The SDK fixture proves the math; it carries no on-chain proof. Before
real deposits: take one real Polymarket Safe user, derive with our
Python code, and confirm via Polygon RPC `eth_getCode` (or Polygonscan
internal txns from `0xaacFeEa0…`) that the deployed Safe sits at
exactly the derived address, and that the user is on the Safe (not
Magic/email) path.

## P1 — DONE (corrected)

Backend: `GET /trading/wallet/deposit-address` (counterfactual CREATE2,
no gas/key/deploy) + `GET /trading/wallet/deposit-balance` (free
USDC.e `eth_call`). Frontend: `DepositModal` with the Polymarket-tip
guide + a 10 s balance poll showing "X USDC.e reçus ⚡" the moment a
tip lands. Works with **zero** builder key / signature / MetaMask —
also unblocks operator self-testing. Highest-value path: our target
user already has funds on Polymarket and can tip their own
counterfactual Safe in ~1 min.

## P2 — Gasless Safe deploy (UNBLOCKED — real spec)

Use Polymarket's public client, do **not** hand-roll the meta-tx.

- **`@polymarket/builder-relayer-client`** (TS) / `py-builder-relayer-client`
  (Python). `RelayClient(relayerUrl, chainId=137, signer, builderConfig)`
  exposes `getDeployed()` (is the Safe on-chain yet?) and `deploy()`
  (relayer pays gas; one EIP-712 signature proves ownership — no
  `BUILDER_PRIVATE_KEY`, no per-tx gas).
- Relayer endpoint: `https://relayer-v2.polymarket.com/` — docs also
  reference `relayer.polymarket.com`; **confirm the live one** with a
  `getDeployed()` call against a known deployed Safe before wiring the
  deploy path.
- The factory it deploys through is `0xaacFeEa0…` — i.e. exactly the
  P1 `compute_safe_address` derivation (now that it's fixed they
  match; that match is the whole point of the fix).

### Architecture decision (2026-05-19): signer location

The gasless deploy is signed by **whoever holds the signer key**. Two
paths, deliberately split:

- **P2b — user-facing (the real one):** the deploy is signed in the
  **user's own browser wallet** (wagmi + `@polymarket/builder-relayer-client`).
  The backend NEVER holds a user key. Backend only adds builder-HMAC
  attribution headers via the existing `/api/polymarket/sign` →
  `/relayer-rpc/…` proxy. **Not yet built — next PR.**
- **P2a — operator self-test (SHIPPED, gated off):** signs with an
  operator-held key so the operator can validate the end-to-end deploy
  on their OWN wallet before P2b ships. Never acts for a real user.

### P2a — SHIPPED (gated off by default)

- `app/trading/relayer_deployer.py` — `RelayerDeployer` wrapping the
  official `py-builder-relayer-client==0.0.2rc1` (`RelayClient`).
  Three independent gates, all required: `enable_relayer_deploy`
  (master switch, default **False**), `operator_test_private_key`,
  builder HMAC creds. Idempotent (returns the address if already
  deployed). Polls the relayer's authoritative `get_deployed()` rather
  than trust an opaque response.
- **Defense-in-depth:** `_cross_check` aborts the deploy unless the
  SDK's `get_expected_safe()` equals our `compute_safe_address()` —
  the #124 bug class can never recur silently.
- **Triple-verified derivation:** our `compute_safe_address` now
  provably equals (1) Polymarket's published SDK test vector
  (`test_derive.py`) and (2) Polymarket's **live** SDK code
  (`RelayClient.get_expected_safe`, asserted in CI by
  `tests/unit/test_relayer_deployer.py::test_real_sdk_matches_our_derivation`).
- `safe_deployer.deploy_safe` stays a hard-fail (incompatible
  stock-Gnosis path removed in #124). The relayer path is the only
  deploy.
- Settings added: `relayer_url` (default `https://relayer-v2.polymarket.com`),
  `enable_relayer_deploy` (False), `operator_test_private_key` (None).

#### Operator self-test runbook

Host env (all three or the run is refused):
`ENABLE_RELAYER_DEPLOY=true`, `OPERATOR_TEST_PRIVATE_KEY=0x…` (your
test EOA), `BUILDER_API_KEY/SECRET/PASSPHRASE`. Then:

```
# dry run — derive + cross-check + is-deployed, NO deploy:
docker compose exec app python -m scripts.relayer_selftest --check
# actually deploy (gasless, mainnet, idempotent):
docker compose exec app python -m scripts.relayer_selftest
```

### P2b — frontend user-sign (next PR)

- `@polymarket/builder-relayer-client` in the browser with the wagmi
  signer; user signs the `CreateProxy` EIP-712 once.
- `WalletSetupModal`: replace the MetaMask ownership-proof tx with the
  single relayer EIP-712 signature; builder headers from the backend
  proxy.
- `native_trading_available` (PR #119) flips True off **relayer
  reachability**, not off a builder key.

Estimate P2b: ~3–4 days (spec known, P2a proved the integration).

## P3 — Bridge (first-party, NOT a 3rd-party widget)

Earlier note recommended LI.FI — **superseded**. Polymarket runs its
own first-party bridge: `bridge.polymarket.com`, `POST /deposit
{address}` returns a per-user deposit address that auto-swaps inbound
tokens/chains → USDC.e on Polygon to the target address. Destination =
the P1 counterfactual Safe address (we already derive it). No
3rd-party SDK, no provider account, no extra fee model to accept.

Backend: surface the bridge deposit address (small proxy through the
existing HMAC route or a thin server call). Frontend: a panel in the
deposit modal alongside the Polymarket-tip path. ~3–4 days. Can
proceed independently of the edge verdict (low-risk, mostly
frontend).

## P4 — API-key trading (buildable; P2 at runtime)

`useClobClient.ts` already wires `builderConfig` +
`createOrDeriveApiKey`; the backend `/api/polymarket/sign` proxy is
live. Use **`@polymarket/clob-client`** `ClobClient.deriveApiKey()` /
`createApiKey()` (EIP-712 `ClobAuthDomain`, `signatureType=2` =
Safe-funder). Derive once, cache the CLOB creds, and subsequent orders
need no MetaMask popup (betmoar's "API Key" step).

- Returns `{ready:false, reason:"safe_not_deployed"}` until the Safe
  exists → **runtime dependency on P2**.
- The `/auth/` path is already allow-listed; the derive-and-cache flow
  is what's missing.

Token approvals to batch once (Safe → Polymarket spenders), all on
Polygon:
- USDC.e `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- CTF `0x4d97dcd97ec945f40cf65f87097ace5ea0476045`
- Spenders: CTF Exchange `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E`,
  NegRisk CTF Exchange `0xC5d563A36AE78145C45a50134d48A1215220f80a`,
  NegRisk Adapter `0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296`.

Build P4 only after P2 lands and the post-H+72 edge verdict is
positive — frictionless execution for a non-profitable pipeline just
automates losses.

## Sequencing decision

1. **Now → H+72**: P1 shipped + **fixed**. P2/P3/P4 may now be built
   from the verified public spec so onboarding is *ready* when real
   users arrive (operator's explicit ask 2026-05-19) — but **not
   enabled for real money** until the gate below.
2. **At H+72 (2026-05-21)**: read the levier 1/2/3 verdict.
   - Edge positive → enable P2 (after the live-RPC verification gate),
     then P3, then P4.
   - Edge not positive → pivot product/positioning before enabling
     real-money execution.
3. P3 (bridge) can proceed independently — low-risk, mostly frontend.

**The honest call: P1 was the 80/20 and its derivation bug is now
fixed and proven against Polymarket's own test vector. P2–P4 are now
real (not speculative) engineering against a public, verified spec —
build the plumbing now, gate the money switch on the proven edge.**
