/**
 * P3 — Polymarket's FIRST-PARTY bridge (any token/any chain → USDC.e
 * on Polygon). NOT a third-party widget (LI.FI/Relay/etc.).
 *
 * `https://bridge.polymarket.com` is a Polymarket-hosted proxy over
 * fun.xyz. Source-verified (docs.polymarket.com/api-reference/bridge):
 *   POST /deposit {address}        — no auth (`security: []`)
 *     → 201 { address: {evm,svm,btc,tvm}, note }
 *   GET  /status/{depositAddress}  — no auth
 *     → { transactions: [{ toChainId, toTokenAddress, status, ... }] }
 *
 * `address` we submit = the user's proxy-Safe (our triple-verified
 * CREATE2 address from /trading/wallet/deposit-address). The service
 * derives per-user, per-chain deposit addresses that auto-forward and
 * settle as USDC.e on Polygon (137) to that Safe.
 *
 * Calls go DIRECT browser→bridge (no auth ⇒ no backend proxy, no
 * allow-list change). UNVERIFIED: browser-origin CORS for
 * bridge.polymarket.com is not documented — callers MUST degrade
 * gracefully (the P1 Polymarket-tip path + on-chain USDC.e balance
 * poll remain the robust funded path if this is unreachable).
 */

const BRIDGE_BASE = "https://bridge.polymarket.com"
// Don't hang the modal if the bridge host is slow/unreachable.
const BRIDGE_TIMEOUT_MS = 12_000

export type BridgeDepositAddresses = {
  /** EVM deposit address (the one we surface — send from any EVM chain). */
  evm: string
  svm?: string
  btc?: string
  tvm?: string
}

async function bridgeFetch(path: string, init?: RequestInit): Promise<Response> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), BRIDGE_TIMEOUT_MS)
  try {
    return await fetch(`${BRIDGE_BASE}${path}`, { ...init, signal: ctrl.signal })
  } finally {
    clearTimeout(t)
  }
}

/**
 * Create per-chain deposit addresses that forward into `safeAddress`
 * as USDC.e on Polygon. `safeAddress` = the user's proxy-Safe.
 * Throws on non-2xx / network / CORS / timeout — callers fall back to
 * the Polymarket-tip path.
 */
export async function createBridgeDeposit(
  safeAddress: string,
): Promise<BridgeDepositAddresses> {
  const res = await bridgeFetch("/deposit", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ address: safeAddress }),
  })
  if (!res.ok) throw new Error(`bridge /deposit HTTP ${res.status}`)
  const data = (await res.json()) as { address?: BridgeDepositAddresses }
  if (!data?.address?.evm) {
    throw new Error("bridge /deposit: malformed response (no evm address)")
  }
  return data.address
}

export type BridgeTxStatus =
  | "DEPOSIT_DETECTED"
  | "PROCESSING"
  | "ORIGIN_TX_CONFIRMED"
  | "SUBMITTED"
  | "COMPLETED"
  | "FAILED"

export type BridgeStatus = {
  transactions: Array<{
    status: BridgeTxStatus
    toChainId?: string
    toTokenAddress?: string
    txHash?: string
    fromChainId?: string
  }>
}

/** Poll progress for a deposit address from `createBridgeDeposit`.
 *  Best-effort: the authoritative "funds arrived" signal remains the
 *  existing on-chain USDC.e balance poll on the Safe. */
export async function getBridgeStatus(
  depositAddress: string,
): Promise<BridgeStatus> {
  const res = await bridgeFetch(`/status/${depositAddress}`)
  if (!res.ok) throw new Error(`bridge /status HTTP ${res.status}`)
  return (await res.json()) as BridgeStatus
}
