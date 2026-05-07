/**
 * useClobClient — initialize a Polymarket CLOB client wired to:
 *   1. the user's MetaMask via viem (signs each EIP-712 order)
 *   2. our /api/polymarket/sign endpoint for Foresight builder
 *      attribution (server-side HMAC, secret never reaches the browser)
 *
 * Why this hook exists
 * --------------------
 * The Polymarket Builder integration requires every CLOB request to
 * carry 4 builder headers (POLY_BUILDER_*) computed from a SECRET that
 * MUST NOT live in the browser. The clob-client supports this via
 * `BuilderConfig.remoteBuilderConfig.url` — it'll POST {method, path,
 * body} to that URL, expect the 4 headers in the response, and splat
 * them into the actual CLOB request.
 *
 * The hook returns `null` until the user is fully wallet-connected with
 * a Safe deployed; downstream `OrderForm` should disable the "Place
 * order" button while `client === null`.
 *
 * Lifecycle
 * ---------
 * On every wallet/safe change we recreate the client. We DO NOT cache
 * across wallet swaps — the funder address is baked into the client
 * construction, so a stale client would route orders to the wrong
 * Safe.
 *
 * References
 * ----------
 *   docs.polymarket.com/api-reference/authentication
 *   github.com/Polymarket/wagmi-safe-builder-example/blob/main/hooks/useClobClient.ts
 */
import { useMemo } from "react"
import { useAccount, useWalletClient } from "wagmi"

import { walletClientToEthersSigner } from "@/lib/walletClientToEthersSigner"

import type { ClobClient as ClobClientType } from "@polymarket/clob-client"

const CLOB_HOST = "https://clob.polymarket.com"
const POLYGON_CHAIN_ID = 137

// Origin-relative path; Caddy proxies /api/* to the FastAPI backend.
// Using a relative URL keeps prod and dev (Vite proxy) on the same code.
const REMOTE_SIGNING_URL = "/api/polymarket/sign"

// signature_type=2 → Safe proxy (the user's Polymarket Gnosis Safe is
// the funder; the EOA is the only owner / signer). signature_type=0
// would be a direct EOA — wrong for the Polymarket Safe model.
const SIGNATURE_TYPE_SAFE = 2

type UseClobClientReturn = {
  client: ClobClientType | null
  ready: boolean
  reason: string | null
}

export function useClobClient({
  safeAddress,
}: {
  safeAddress: string | null | undefined
}): UseClobClientReturn {
  const { isConnected } = useAccount()
  const { data: walletClient } = useWalletClient({ chainId: POLYGON_CHAIN_ID })

  return useMemo<UseClobClientReturn>(() => {
    if (!isConnected) {
      return { client: null, ready: false, reason: "wallet_not_connected" }
    }
    if (!walletClient) {
      // walletClient resolves async after `useAccount` flips to true —
      // brief window where we're connected but the client hasn't rehydrated.
      return { client: null, ready: false, reason: "wallet_client_not_ready" }
    }
    if (!safeAddress) {
      return { client: null, ready: false, reason: "safe_not_deployed" }
    }

    // Defer the heavy import — clob-client + ethers ship ~150 KB; pull
    // them only when the user actually has a wallet connected.
    let signer
    try {
      signer = walletClientToEthersSigner(walletClient)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { client: null, ready: false, reason: `signer_adapter: ${msg}` }
    }

    // Lazy require — top-level import would force this whole module
    // (and its 150 KB transitive payload) into the eager bundle on
    // every page that imports useClobClient. Keep it inside the hook
    // body so only the wallet path pulls it.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { ClobClient } = require("@polymarket/clob-client") as typeof import("@polymarket/clob-client")
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { BuilderConfig } = require("@polymarket/clob-client/dist/builder/builder") as {
      BuilderConfig: new (cfg: { remoteBuilderConfig: { url: string } }) => unknown
    }

    let builderConfig: unknown
    try {
      builderConfig = new BuilderConfig({
        remoteBuilderConfig: { url: REMOTE_SIGNING_URL },
      })
    } catch (e) {
      // If the builder/builder path is gone (clob-client bumps), surface
      // the error rather than silently dropping attribution.
      console.warn("BuilderConfig init failed; orders will not be attributed:", e)
      builderConfig = undefined
    }

    let client: ClobClientType
    try {
      // ClobClient ctor positional args (clob-client v5.x):
      //   (host, chain, signer, creds, signatureType, funderAddress,
      //    geoBlockToken?, useServerTime?, builderConfig?)
      // We pass `creds=undefined` — the client will derive them from
      // the EOA on first call (`createOrDeriveApiKey`), then cache for
      // the session. That avoids Foresight ever holding the user's
      // L2 API credentials.
      client = new ClobClient(
        CLOB_HOST,
        POLYGON_CHAIN_ID,
        signer,
        undefined, // creds — derived on first signed call
        SIGNATURE_TYPE_SAFE,
        safeAddress, // funder
        undefined, // geoBlockToken
        false, // useServerTime
        builderConfig as never,
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      return { client: null, ready: false, reason: `clob_init: ${msg}` }
    }

    return { client, ready: true, reason: null }
  }, [isConnected, walletClient, safeAddress])
}
