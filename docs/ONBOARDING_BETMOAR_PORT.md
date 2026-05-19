# Onboarding port — betmoar.fun model → Foresight

Status as of 2026-05-19. Source of truth for the wallet-onboarding
roadmap. betmoar.fun is a fellow Polymarket Builder Program site whose
onboarding is the UX gold standard for our exact target (Polymarket
traders).

## The 4 phases

| Phase | What | Status |
|---|---|---|
| **P1** | Polymarket-tip deposit (counterfactual addr + on-chain confirm) | ✅ **SHIPPED** (PR #121 + balance poll) |
| **P2** | Gasless Safe deploy via Polymarket relayer | ⛔ **BLOCKED on external docs** |
| **P3** | Bridge widget (any token/chain → USDC.e) | 🟡 needs provider decision |
| **P4** | API-key trading (no per-order signature) | ⛔ depends on P2 |

## P1 — DONE

Backend: `GET /trading/wallet/deposit-address` (counterfactual CREATE2,
no gas/key/deploy) + `GET /trading/wallet/deposit-balance` (free
USDC.e `eth_call`). Frontend: `DepositModal` with the Polymarket-tip
guide + a 10 s balance poll showing "X USDC.e reçus ⚡" the moment a
tip lands. Works with **zero** builder key / signature / MetaMask —
also unblocks operator self-testing.

This already covers the highest-value path: our target user has funds
on Polymarket and can tip their own counterfactual Safe in ~1 min.

## P2 — Gasless Safe deploy (BLOCKED — do NOT write speculative code)

### Why it's blocked

The only Safe deploy that exists is `safe_deployer.deploy_safe()`,
which pays gas from `BUILDER_PRIVATE_KEY` and requires the user to
sign an ownership-proof tx (the flow that failed on 2026-05-18).
betmoar deploys **gasless via the Polymarket relayer** — no key, no
signature.

`app/api/routes/polymarket_signing.py` only has `/relayer-rpc/` in
its **HMAC proxy allow-list** — that's a door, not an implementation.
There is no relayer-deploy code anywhere in the repo.

Implementing the relayer deploy correctly requires the **exact
Polymarket relayer protocol** (endpoints, payload schema, the
meta-transaction signature scheme, the Safe factory call it
bundles). None of this is in the repo. Writing it from guesswork
would be untestable speculative code — the opposite of every other
change this sprint (each measured/backtested before ship).

### Pre-requisites to unblock (operator/external, not code)

1. **Polymarket relayer API docs** — the official reference for
   `relayer-rpc` deploy. Polymarket's `wagmi-safe-builder-example`
   (referenced in `polymarket_signing.py` header) is the canonical
   pattern; obtain that repo/example.
2. Confirm the relayer covers gas (it should — that's the point) and
   the exact `(safe init, saltNonce)` it expects vs our
   `compute_safe_address` derivation. They MUST match or the
   counterfactual address from P1 won't be the one the relayer
   deploys.
3. A staging/testnet path to verify a deploy end-to-end before prod.

### Implementation sketch (once docs in hand)

- New `app/trading/relayer_deployer.py`: builds the relayer
  meta-tx, POSTs through the existing HMAC-signed proxy
  (`/api/polymarket/sign` → `/relayer-rpc/...`), polls for the
  deploy tx receipt.
- `safe_deployer.deploy_safe` becomes a fallback; the relayer path
  is primary and needs no `BUILDER_PRIVATE_KEY`.
- `WalletSetupModal` flow: drop the MetaMask ownership signature
  step (relayer proves ownership differently — TBD by the docs).
- `native_trading_available` (PR #119) flips True off the relayer
  being reachable, not off a builder key.

Estimate once unblocked: ~1-1.5 weeks.

## P3 — Bridge widget (needs a provider decision)

betmoar embeds a "bridge any token from 14+ chains → USDC.e on
Polygon" widget with a dedicated deposit address. This is a
third-party SDK, not something to hand-roll.

### Decision needed (product, not code)

Pick one provider, get an API key, accept its fee model:
- **LI.FI** — widest chain/token coverage, embeddable React widget
- **Across** — cheapest for EVM↔EVM, narrower token set
- **Squid (Axelar)** — good UX, Cosmos+EVM
- **deBridge** — fast, growing

Recommendation: **LI.FI widget** — drop-in React component, 14+
chains like betmoar, destination = the P1 counterfactual address
(already have it). ~3-5 days once the provider + key are chosen.

No backend work beyond surfacing the destination address (P1 already
does). Purely a frontend widget integration + provider account.

## P4 — API-key trading (depends on P2)

`useClobClient.ts` already wires `builderConfig` +
`createOrDeriveApiKey` and the backend `/api/polymarket/sign`
proxy is live. But:

- It returns `{ready:false, reason:"safe_not_deployed"}` until the
  Safe exists → **hard dependency on P2**.
- Today every order still needs a MetaMask EIP-712 signature.
  betmoar's "API Key" step derives a CLOB key so subsequent orders
  need no wallet popup. The `/auth/` path is allow-listed but the
  derive-and-cache flow isn't built.

Do P4 only after P2 lands and the post-H+72 edge verdict is
positive — building frictionless execution for a non-profitable
pipeline automates losses.

## Sequencing decision

1. **Now → H+72**: P1 is shipped and sufficient for testing +
   demoing. Do NOT speculatively code P2/P4.
2. **At H+72 (2026-05-21)**: read the levier 1/2/3 verdict.
   - Edge confirmed positive → invest in P2 (get the Polymarket
     relayer docs first) then P3, then P4.
   - Edge not positive → pivot product/positioning before sinking
     1-2 weeks into onboarding for a pipeline that doesn't pay.
3. P3 (bridge) can proceed independently of the edge verdict if a
   provider is chosen — it's low-risk frontend-only, but lower
   priority than proving the edge.

**The honest call: P1 was the 80/20. P2-P4 are real engineering that
need external API docs + a proven edge before they're worth it.
Shipping speculative relayer code now would violate the same rigor
(measure/verify before ship) applied to every levier this sprint.**
