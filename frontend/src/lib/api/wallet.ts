import { apiGet, apiPost } from "@/lib/api/client"

export type WalletStatus = {
  connected: boolean
  eoa_address: string | null
  safe_address: string | null
}

export type ConnectResponse = {
  safe_address: string
}

/** One-shot signing challenge issued by the backend.
 *
 * The user must sign `message` with their EOA private key and POST the
 * `(eoa_address, nonce, signature)` triple back to `/wallet/connect`.
 * Without the signature the backend refuses to deploy a Safe — this
 * prevents an attacker from registering arbitrary EOAs and draining
 * the builder wallet's MATIC. Audit P0-3, 2026-04-27.
 */
export type WalletNonce = {
  nonce: string
  message: string
  expires_in_seconds: number
}

export async function getWalletStatus(): Promise<WalletStatus> {
  return apiGet<WalletStatus>("/trading/wallet/status")
}

export async function getWalletNonce(): Promise<WalletNonce> {
  return apiGet<WalletNonce>("/trading/wallet/nonce")
}

export async function connectWallet(args: {
  eoa_address: string
  nonce: string
  signature: string
}): Promise<ConnectResponse> {
  return apiPost<ConnectResponse>("/trading/wallet/connect", args)
}
