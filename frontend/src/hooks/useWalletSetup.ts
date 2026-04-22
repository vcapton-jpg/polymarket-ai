import { useCallback, useEffect, useState } from "react"
import { useAccount, useConnect } from "wagmi"
import { injected } from "wagmi/connectors"
import { getWalletStatus, connectWallet, type WalletStatus } from "@/lib/api/wallet"
import { hasToken } from "@/lib/api/auth"

export type SetupStep = "idle" | "connecting_wallet" | "deploying_safe" | "done" | "error"

type UseWalletSetupReturn = {
  walletConnected: boolean
  safeAddress: string | null
  eoaAddress: string | null
  step: SetupStep
  error: string | null
  startSetup: () => Promise<void>
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
      let eoa = connectedAddress
      if (!eoa) {
        const result = await connectAsync({ connector: injected() })
        eoa = result.accounts[0]
      }
      if (!eoa) throw new Error("Wallet connection refused")

      setStep("deploying_safe")
      const resp = await connectWallet(eoa as string)

      setStatus({ connected: true, eoa_address: eoa as string, safe_address: resp.safe_address })
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
