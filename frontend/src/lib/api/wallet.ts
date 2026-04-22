import { apiGet, apiPost } from "@/lib/api/client"

export type WalletStatus = {
  connected: boolean
  eoa_address: string | null
  safe_address: string | null
}

export type ConnectResponse = {
  safe_address: string
}

export async function getWalletStatus(): Promise<WalletStatus> {
  return apiGet<WalletStatus>("/trading/wallet/status")
}

export async function connectWallet(eoa_address: string): Promise<ConnectResponse> {
  return apiPost<ConnectResponse>("/trading/wallet/connect", { eoa_address })
}
