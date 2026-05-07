/**
 * Adapter: wagmi viem `WalletClient` -> ethers v5 `Signer`.
 *
 * Why this exists
 * ---------------
 * Our stack is wagmi 2.x + viem 2.x. The Polymarket clob-client (v5.x,
 * the stable line at 2026-05-07) takes an ethers v5 `Signer`. Without
 * this adapter we'd either downgrade to wagmi 1.x (v1 used ethers
 * natively — but that's a 6-months-old codebase) or wait for the v2
 * Polymarket clob-client to mature.
 *
 * The adapter is the same pattern the official wagmi-safe-builder-example
 * uses, expressed in ~20 lines.
 *
 * Usage
 * -----
 *   const { data: walletClient } = useWalletClient()
 *   const signer = walletClient ? walletClientToEthersSigner(walletClient) : null
 *   const clob = signer ? new ClobClient(host, chain, signer, …) : null
 */
import { providers } from "ethers"
import type { WalletClient } from "viem"

export function walletClientToEthersSigner(walletClient: WalletClient) {
  const { account, chain, transport } = walletClient
  if (!account || !chain) {
    throw new Error(
      "walletClientToEthersSigner: walletClient missing account or chain — " +
        "is the wallet actually connected?",
    )
  }
  const network = {
    chainId: chain.id,
    name: chain.name,
    // Polygon doesn't have ENS; leave undefined so ethers doesn't try.
    ensAddress: chain.contracts?.ensRegistry?.address,
  }
  // `transport` here is the EIP-1193-shaped object viem exposes; ethers'
  // Web3Provider can wrap it directly. Each call goes through the
  // injected MetaMask under the hood (signTypedData_v4 for orders,
  // sendTransaction for Safe ops).
  const provider = new providers.Web3Provider(transport as never, network)
  return provider.getSigner(account.address)
}
