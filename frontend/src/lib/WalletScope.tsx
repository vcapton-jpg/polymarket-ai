/**
 * Local wagmi/viem scope.
 *
 * Until April 2026 the Wagmi provider was mounted at the React root in
 * `main.tsx`. That pulled wagmi (~80 KB raw) and viem (~200 KB raw) into
 * the eager `index` chunk for *every* visit, even on the public homepage
 * where no wallet is touched. Only two surfaces use the wallet — the real-
 * trade `OrderForm` (mounted from `SignalDetail`) and the Settings wallet
 * section — and both live in lazy route chunks.
 *
 * Mounting the provider locally inside those consumers means Vite tree-
 * splits wagmi into the SignalDetail + Settings chunks. The main bundle
 * loses the cost; the wallet code is paid for only when a wallet UI is
 * actually about to render.
 *
 * If a third surface ever needs the wallet, wrap it the same way rather
 * than promoting WagmiProvider back to the root — the eager-load tax was
 * the whole reason we moved.
 */
import type { ReactNode } from "react"
import { WagmiProvider } from "wagmi"
import { wagmiConfig } from "./wagmiConfig"

export function WalletScope({ children }: { children: ReactNode }) {
  return <WagmiProvider config={wagmiConfig}>{children}</WagmiProvider>
}
