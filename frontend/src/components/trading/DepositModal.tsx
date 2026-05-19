import { useCallback, useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import FocusLock from "react-focus-lock"
import { Check, Copy, ExternalLink, Gift, Loader2, Wallet, X } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { getDepositAddress } from "@/lib/api/wallet"
import { useToasts } from "@/lib/useToasts"

type Props = {
  open: boolean
  onClose: () => void
  /** The user's connected EOA. Required to derive the counterfactual
   *  Safe address — no signature, no gas, no deploy needed. */
  eoa: string | null
}

/**
 * Deposit screen — P1 of the betmoar.fun-inspired onboarding.
 *
 * The cheapest, highest-impact win: our target user (Polymarket
 * traders) already has funds on Polymarket. Instead of forcing a
 * bridge/onramp we show their (counterfactual) Safe address and walk
 * them through tipping it from their own Polymarket profile — 1 min,
 * zero gas, zero new crypto, zero MetaMask. The Safe doesn't even need
 * to be deployed yet: CREATE2 makes the address deterministic, funds
 * sent there are safe, deployment happens lazily at first trade.
 *
 * Bridge / onramp = P3, intentionally out of scope here.
 */
export function DepositModal({ open, onClose, eoa }: Props) {
  const { addToast } = useToasts()
  const [address, setAddress] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const close = useCallback(() => onClose(), [onClose])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, close])

  useEffect(() => {
    if (!open || !eoa) return
    let cancelled = false
    setLoading(true)
    setError(null)
    getDepositAddress(eoa)
      .then((r) => {
        if (!cancelled) setAddress(r.deposit_address)
      })
      .catch(() => {
        if (!cancelled)
          setError("Impossible de récupérer ton adresse. Réessaie.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, eoa])

  const copy = async () => {
    if (!address) return
    try {
      await navigator.clipboard.writeText(address)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      addToast({
        type: "info",
        title: "Copie impossible",
        description: "Sélectionne et copie l'adresse manuellement.",
      })
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
          onClick={(e) => e.target === e.currentTarget && close()}
        >
          <FocusLock returnFocus>
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="deposit-title"
              initial={{ opacity: 0, scale: 0.95, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 8 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-md rounded-2xl border border-line-strong bg-obsidian-900 p-6 shadow-2xl"
            >
              <button
                type="button"
                onClick={close}
                className="absolute right-4 top-4 rounded-md p-1 text-ink-dim hover:text-ink transition-colors"
                aria-label="Fermer"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-brand-500/40 bg-brand-500/10">
                <Wallet className="h-6 w-6 text-brand-400" />
              </div>

              <h2
                id="deposit-title"
                className="mb-1 font-display text-lg font-semibold text-ink"
              >
                Déposer sur ton wallet
              </h2>
              <p className="mb-5 text-sm text-ink-muted">
                Le plus simple si tu as déjà un compte Polymarket : tippe
                ton propre wallet. 1 minute, zéro gas, zéro MetaMask.
              </p>

              {/* Polymarket tip — the easy path */}
              <div className="mb-5 rounded-xl border border-brand-500/25 bg-brand-500/[0.04] p-4">
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-brand-300">
                  <Gift className="h-4 w-4" />
                  Tip via Polymarket — recommandé
                </div>
                <ol className="space-y-1.5 text-sm text-ink-muted">
                  <li>
                    <span className="text-brand-300">1.</span> Ouvre ton
                    profil Polymarket
                  </li>
                  <li>
                    <span className="text-brand-300">2.</span> Clique le
                    bouton 🎁 <span className="text-ink">Send Tip</span>
                  </li>
                  <li>
                    <span className="text-brand-300">3.</span> Colle
                    l'adresse ci-dessous, entre le montant, confirme
                  </li>
                  <li>
                    <span className="text-brand-300">4.</span> Les fonds
                    arrivent en ~1 min ⚡
                  </li>
                </ol>
                <a
                  href="https://polymarket.com/profile"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 inline-flex items-center gap-1.5 text-sm font-medium text-brand-400 hover:text-brand-300 transition-colors"
                >
                  Ouvrir mon profil Polymarket
                  <ExternalLink className="h-3.5 w-3.5" />
                </a>
              </div>

              {/* Safe address */}
              <p className="mb-1.5 text-label-xs uppercase tracking-wide text-ink-dim">
                Ton adresse de dépôt
              </p>
              {loading ? (
                <div className="flex items-center gap-2 rounded-lg border border-line-strong bg-obsidian-850 px-3 py-3 text-sm text-ink-muted">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Récupération de ton adresse…
                </div>
              ) : error ? (
                <p
                  role="alert"
                  className="rounded-lg border border-signal-no/40 bg-signal-no/10 px-3 py-2 text-sm text-signal-no"
                >
                  {error}
                </p>
              ) : address ? (
                <button
                  type="button"
                  onClick={copy}
                  className="group flex w-full items-center justify-between gap-2 rounded-lg border border-line-strong bg-obsidian-850 px-3 py-3 text-left transition-colors hover:border-brand-400/40"
                >
                  <span className="num truncate font-mono text-sm text-ink">
                    {address}
                  </span>
                  {copied ? (
                    <Check className="h-4 w-4 shrink-0 text-signal-yes" />
                  ) : (
                    <Copy className="h-4 w-4 shrink-0 text-ink-dim group-hover:text-ink" />
                  )}
                </button>
              ) : (
                <p className="rounded-lg border border-line-strong bg-obsidian-850 px-3 py-3 text-sm text-ink-dim">
                  Connecte ton wallet d'abord pour générer ton adresse.
                </p>
              )}

              <p className="mt-3 text-label-xs leading-relaxed text-ink-dim">
                Cette adresse est déterministe et t'appartient — tu peux
                y envoyer des fonds même avant le premier trade. Bridge
                depuis d'autres chaînes : bientôt.
              </p>

              <Button
                variant="secondary"
                size="lg"
                className="mt-5 w-full"
                onClick={close}
              >
                J'ai compris
              </Button>
            </motion.div>
          </FocusLock>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
