import { useCallback, useEffect, useState } from "react"
import { useAccount, useConnect, useSignMessage } from "wagmi"
import { injected } from "wagmi/connectors"
import {
  getWalletStatus,
  getWalletNonce,
  connectWallet,
  type WalletStatus,
} from "@/lib/api/wallet"
import { hasToken } from "@/lib/api/auth"

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
  step: SetupStep
  error: string | null
  startSetup: () => Promise<void>
  refreshStatus: () => Promise<void>
}

/**
 * Wallet setup flow (post-2026-04-27 P0-3 audit):
 *
 *   1. Connect wallet (MetaMask injected) — obtain EOA address.
 *   2. Ask backend for a one-shot signing nonce (`GET /wallet/nonce`).
 *   3. Ask the wallet to sign the returned message via `personal_sign`.
 *   4. POST `(eoa, nonce, signature)` to `/wallet/connect`. Backend
 *      verifies the signature recovers to the supplied EOA, then
 *      pays gas to deploy a Polymarket Safe.
 *
 * Pre-fix the connect endpoint accepted `eoa_address` only — letting an
 * authenticated attacker register arbitrary EOAs without proof of
 * control and drain the builder wallet's MATIC.
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

      // Step 2 + 3: signature challenge — proves to the backend that
      // the caller controls the private key for `eoa` BEFORE any gas
      // is paid. Skip would let an attacker drain the builder wallet.
      setStep("signing_challenge")
      const challenge = await getWalletNonce()
      const signature = await signMessageAsync({
        account: eoa as `0x${string}`,
        message: challenge.message,
      })

      setStep("deploying_safe")
      const resp = await connectWallet({
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
  }, [connectedAddress, connectAsync, signMessageAsync])

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
