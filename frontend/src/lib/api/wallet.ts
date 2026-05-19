import { apiGet, apiPost } from "@/lib/api/client"

export type WalletStatus = {
  connected: boolean
  eoa_address: string | null
  safe_address: string | null
  /** Backend can actually deploy a Safe (builder key configured).
   *  When false, the native-trading CTA must be gated so the user
   *  never signs a MetaMask tx that's guaranteed to fail at deploy. */
  native_trading_available?: boolean
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

/** Counterfactual deposit address — funds can be sent here BEFORE the
 *  Safe is deployed (no gas, no signature, no builder key). P1 of the
 *  betmoar-inspired onboarding. */
export type DepositAddress = {
  deposit_address: string
  deployed: boolean
}

export async function getDepositAddress(eoa: string): Promise<DepositAddress> {
  return apiGet<DepositAddress>(
    `/trading/wallet/deposit-address?eoa=${encodeURIComponent(eoa)}`,
  )
}

/** Live USDC.e balance of the deposit address — used by DepositModal
 *  to confirm a Polymarket tip landed ("funds received ✓"). */
export type DepositBalance = {
  usdce_balance: number
}

export async function getDepositBalance(
  address: string,
): Promise<DepositBalance> {
  return apiGet<DepositBalance>(
    `/trading/wallet/deposit-balance?address=${encodeURIComponent(address)}`,
  )
}

export async function connectWallet(args: {
  eoa_address: string
  nonce: string
  signature: string
}): Promise<ConnectResponse> {
  return apiPost<ConnectResponse>("/trading/wallet/connect", args)
}
