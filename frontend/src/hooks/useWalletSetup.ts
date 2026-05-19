import { useCallback, useEffect, useState } from "react"
import { useAccount, useConnect, useSignMessage, useWalletClient } from "wagmi"
import { injected } from "wagmi/connectors"
import {
  getWalletStatus,
  getWalletNonce,
  connectWallet,
  type WalletStatus,
} from "@/lib/api/wallet"
import { deploySafeViaRelayer } from "@/lib/relayerDeploy"
import { hasToken } from "@/lib/api/auth"

/** Absorb RPC propagation lag: the relayer may report the deploy
 *  confirmed a beat before our backend's Polygon node sees the
 *  bytecode. /connect returns 409 until then — retry a few times
 *  before surfacing. */
async function persistSafeWithRetry(args: {
  eoa_address: string
  nonce: string
  signature: string
}) {
  let lastErr: unknown
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      return await connectWallet(args)
    } catch (e) {
      lastErr = e
      const msg = e instanceof Error ? e.message : String(e)
      // Only retry the "not deployed yet / RPC" transient states.
      if (!/not deployed|409|verify|502|retry/i.test(msg)) throw e
      await new Promise((r) => setTimeout(r, 2500))
    }
  }
  throw lastErr
}

export type SetupStep =
  | "idle"
  | "connecting_wallet"
  | "signing_challenge"
  | "deploying_safe"
  | "done"
  | "error"

type UseWalletSetupReturn = {
  walletConnected: boolean
  safeAddress: string | null
  eoaAddress: string | null
  /** Backend can deploy a Safe. When false, callers must NOT open the
   *  setup modal — the deploy step would fail after the user already
   *  signed. Defaults to true so a transient status fetch failure
   *  doesn't hide a feature that does work. */
  nativeTradingAvailable: boolean
  step: SetupStep
  error: string | null
  startSetup: () => Promise<void>
  refreshStatus: () => Promise<void>
}

/**
 * Wallet setup flow — P2b (gasless, browser-signed, 2026-05-19):
 *
 *   1. Connect wallet (MetaMask injected) — obtain EOA address.
 *   2. One-shot nonce (`GET /wallet/nonce`) + `personal_sign` — proves
 *      EOA control to OUR backend (kept from the P0-3 audit fix).
 *   3. Gasless deploy via Polymarket's relayer, signed IN THE BROWSER
 *      (`deploySafeViaRelayer`): the user signs ONE CreateProxy
 *      EIP-712; Polymarket pays gas. No backend key, no MetaMask gas.
 *   4. POST `(eoa, nonce, signature)` to `/wallet/connect` — backend
 *      re-verifies EOA control, derives the Safe with the triple-
 *      verified `compute_safe_address`, confirms it's actually
 *      on-chain, then records it (it never deploys anything itself).
 *
 * The backend deploy path was removed (#124/#125): it produced an
 * address Polymarket's relayer never deploys. Pre-P0-3 the connect
 * endpoint accepted `eoa_address` only — the nonce+signature still
 * guards that.
 */
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
  const { signMessageAsync } = useSignMessage()
  // viem WalletClient on Polygon — the relayer SDK signs the
  // CreateProxy EIP-712 with this (user's own wallet).
  const { data: walletClient } = useWalletClient({ chainId: 137 })

  const refreshStatus = useCallback(async () => {
    if (!hasToken()) return
    try {
      const s = await getWalletStatus()
      setStatus(s)
      if (s.connected) setStep("done")
    } catch {
      // user may not be authenticated yet
    }
  }, [])

  useEffect(() => {
    refreshStatus()
  }, [refreshStatus])

  const startSetup = useCallback(async () => {
    setError(null)
    try {
      setStep("connecting_wallet")

      const hasProvider =
        typeof window !== "undefined" &&
        (window as unknown as { ethereum?: unknown }).ethereum !== undefined
      if (!hasProvider) {
        throw new Error(
          "MetaMask n'est pas installé. Installe l'extension depuis metamask.io puis réessaie.",
        )
      }

      let eoa = connectedAddress
      if (!eoa) {
        const result = await connectAsync({ connector: injected() })
        eoa = result.accounts[0]
      }
      if (!eoa) throw new Error("Connexion au wallet refusée")

      // Step 2: backend EOA-control proof (one personal_sign). Kept
      // from the P0-3 audit fix — guards the persist endpoint.
      setStep("signing_challenge")
      const challenge = await getWalletNonce()
      const signature = await signMessageAsync({
        account: eoa as `0x${string}`,
        message: challenge.message,
      })

      // Step 3: gasless deploy, signed in the user's wallet. One
      // CreateProxy EIP-712 popup; Polymarket's relayer pays gas.
      // Idempotent — `alreadyDeployed` just skips straight to persist.
      setStep("deploying_safe")
      if (!walletClient) {
        throw new Error(
          "Wallet client indisponible. Reconnecte ton wallet et réessaie.",
        )
      }
      await deploySafeViaRelayer(walletClient)

      // Step 4: backend re-verifies EOA control, derives + confirms the
      // Safe on-chain, records it. Retries absorb RPC propagation lag.
      const resp = await persistSafeWithRetry({
        eoa_address: eoa as string,
        nonce: challenge.nonce,
        signature,
      })

      setStatus({
        connected: true,
        eoa_address: eoa as string,
        safe_address: resp.safe_address,
      })
      setStep("done")
    } catch (e: unknown) {
      const raw = e instanceof Error ? e.message : String(e)
      const msg = raw.includes("Provider not found")
        ? "MetaMask n'est pas installé. Installe l'extension depuis metamask.io puis réessaie."
        : raw.toLowerCase().includes("user rejected")
          ? "Signature refusée par l'utilisateur."
          : raw
      setError(msg)
      setStep("error")
    }
  }, [connectedAddress, connectAsync, signMessageAsync, walletClient])

  return {
    walletConnected: status.connected,
    safeAddress: status.safe_address,
    eoaAddress: status.eoa_address,
    // Default true: only treat native trading as unavailable when the
    // backend explicitly says so. A missing field (older backend) or a
    // failed status fetch must not hide a working feature.
    nativeTradingAvailable: status.native_trading_available !== false,
    step,
    error,
    startSetup,
    refreshStatus,
  }
}
