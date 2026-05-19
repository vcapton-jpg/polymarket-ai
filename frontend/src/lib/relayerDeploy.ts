/**
 * P2b — gasless Polymarket Safe deploy, signed IN THE USER'S BROWSER.
 *
 * Architecture (locked 2026-05-19)
 * --------------------------------
 * The user signs ONE EIP-712 `CreateProxy` message in their own wallet
 * (wagmi/viem). Polymarket's relayer pays the gas. Our backend NEVER
 * holds a user key and is not in the deploy path at all (it only
 * records the result afterwards, re-verifying on-chain). Builder
 * attribution is deliberately not wired into the deploy — see below.
 *
 * Source-verified against `@polymarket/builder-relayer-client@0.0.9`:
 *   - ctor(relayerUrl, chainId, signer: viem WalletClient, builderConfig?)
 *   - deploy() builds+signs CreateProxy, POSTs /submit, throws
 *     SAFE_DEPLOYED if the Safe already exists
 *   - resp.wait() polls /transaction → RelayerTransaction | undefined
 *
 * Builder attribution is intentionally OMITTED here. Builder headers
 * are optional for SAFE-CREATE (the SDK's `canBuilderAuth()===false`
 * path deploys fine, just unattributed) and the deploy is a one-time,
 * zero-revenue action — fee-rebate attribution only matters on TRADING,
 * which runs through the separate, already-attributed clob-client path
 * (useClobClient). Wiring a BuilderConfig here is also actively unsafe
 * right now: `@polymarket/builder-signing-sdk` is installed twice
 * (top-level 1.0.0 vs the 0.0.8 relayer-client@0.0.9 pins internally);
 * handing RelayClient a 1.0.0 BuilderConfig it expects to be 0.0.8 is a
 * silent runtime hazard a TS cast would only mask. Skip it.
 *
 * UNVERIFIED (gate before real funds): browser→relayer CORS. The SDK is
 * Node-first; `relayer-v2.polymarket.com` browser-origin CORS is not
 * documented. `relayerUrl` is therefore overridable via
 * `VITE_RELAYER_URL` so we can flip to a backend pass-through without a
 * code change if a live spike shows CORS blocks. The whole user-facing
 * path stays gated server-side (`enable_native_relayer_onboarding`)
 * until that spike passes — so this never traps a user mid-signature.
 */
import type { WalletClient } from "viem"

const DEFAULT_RELAYER_URL = "https://relayer-v2.polymarket.com"
const POLYGON_CHAIN_ID = 137

// STATE_MINED / STATE_CONFIRMED are the success terminals; the SDK's
// wait() returns undefined on STATE_FAILED / timeout.
const SUCCESS_STATES = new Set(["STATE_MINED", "STATE_CONFIRMED"])

export type RelayerDeployResult = {
  /** True if the relayer reported the Safe was already on-chain. */
  alreadyDeployed: boolean
  txHash?: string
}

function relayerUrl(): string {
  const fromEnv = (import.meta.env.VITE_RELAYER_URL as string | undefined)?.trim()
  return fromEnv && fromEnv.length > 0 ? fromEnv : DEFAULT_RELAYER_URL
}

/** Was this thrown because the Safe is already deployed? Idempotent.
 *  The SDK's `SAFE_DEPLOYED` Error is not re-exported from the package
 *  index, so match on its message (stable: "Safe already deployed"). */
function isAlreadyDeployed(e: unknown): boolean {
  const msg = e instanceof Error ? e.message : String(e)
  return /already.*deployed|safe.*deployed/i.test(msg)
}

/**
 * Deploy the connected wallet's Polymarket Safe via the relayer.
 *
 * @param walletClient viem WalletClient from wagmi `useWalletClient()`
 *   — the user signs the CreateProxy EIP-712 with this.
 * Resolves once the relayer confirms the deploy on-chain (or the Safe
 * was already deployed). Throws on user-rejection, relayer failure, or
 * unconfirmed deploy — callers surface the message.
 */
export async function deploySafeViaRelayer(
  walletClient: WalletClient,
): Promise<RelayerDeployResult> {
  // Lazy require — the relayer SDK + ethers/viem transitive payload is
  // heavy; only pull it when a user actually runs wallet setup. Mirrors
  // the established useClobClient pattern.
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const relayer = require("@polymarket/builder-relayer-client") as typeof import("@polymarket/builder-relayer-client")

  // No builderConfig (4th arg) — see file header: optional for deploy,
  // and the dual-installed signing-sdk makes passing one unsafe today.
  const client = new relayer.RelayClient(
    relayerUrl(),
    POLYGON_CHAIN_ID,
    walletClient,
  )

  let resp
  try {
    resp = await client.deploy()
  } catch (e) {
    if (isAlreadyDeployed(e)) {
      return { alreadyDeployed: true }
    }
    throw e
  }

  const tx = await resp.wait()
  if (!tx || !SUCCESS_STATES.has(tx.state)) {
    throw new Error(
      "Le déploiement n'a pas été confirmé par le relayer Polymarket. " +
        "Réessaie dans un instant.",
    )
  }
  return { alreadyDeployed: false, txHash: tx.transactionHash }
}
