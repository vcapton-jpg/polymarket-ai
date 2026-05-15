import { useCallback, useEffect } from "react"
import { AnimatePresence, motion } from "framer-motion"
import FocusLock from "react-focus-lock"
import { CheckCircle, Loader2, Wallet, X } from "lucide-react"
import { Button } from "@/components/ui/Button"
import type { SetupStep } from "@/hooks/useWalletSetup"
import { cn } from "@/lib/utils"

type Props = {
  open: boolean
  onSuccess: () => void
  onClose: () => void
  // Wallet setup state passed from parent
  step: SetupStep
  error: string | null
  startSetup: () => Promise<void>
}

const STEPS = [
  { id: "connecting_wallet", label: "Connecte ton wallet (MetaMask)" },
  { id: "signing_challenge", label: "Signe la preuve de propriété" },
  { id: "deploying_safe", label: "Déploiement de ton Safe Polymarket" },
  { id: "done", label: "Dépose des USDC dans ton Safe" },
] as const

const STEP_ORDER = [
  "idle",
  "connecting_wallet",
  "signing_challenge",
  "deploying_safe",
  "done",
  "error",
] as const

export function WalletSetupModal({ open, onSuccess, onClose, step, error, startSetup }: Props) {
  const close = useCallback(() => {
    onClose()
  }, [onClose])

  useEffect(() => {
    if (step === "done") {
      const t = setTimeout(onSuccess, 800)
      return () => clearTimeout(t)
    }
  }, [step, onSuccess])

  // Escape closes — matches the EndOfTrialModal / ConfirmDeleteAccountModal
  // a11y pattern. Skipped during the actual on-chain deploy step because
  // dismissing mid-tx would leave the wallet/Safe in a half-committed state
  // the user can't easily recover from.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && step !== "deploying_safe") close()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, close, step])

  const currentIdx = STEP_ORDER.indexOf(step)
  const isLoading =
    step === "connecting_wallet" ||
    step === "signing_challenge" ||
    step === "deploying_safe"

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={(e) => e.target === e.currentTarget && close()}
        >
          <FocusLock returnFocus>
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="wallet-setup-title"
              aria-describedby="wallet-setup-description"
              aria-busy={isLoading}
              initial={{ opacity: 0, scale: 0.95, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 8 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-sm rounded-2xl border border-line-strong bg-obsidian-900 p-6 shadow-2xl"
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
                {step === "done" ? (
                  <CheckCircle className="h-6 w-6 text-signal-yes" />
                ) : (
                  <Wallet className="h-6 w-6 text-brand-400" />
                )}
              </div>

              <h2
                id="wallet-setup-title"
                className="mb-1 font-display text-lg font-semibold text-ink"
              >
                {step === "done" ? "Wallet connecté !" : "Active le trading natif"}
              </h2>
              <p
                id="wallet-setup-description"
                className="mb-5 text-sm text-ink-muted"
              >
                {step === "done"
                  ? "Ton Safe Polymarket est prêt. Dépose des USDC pour commencer."
                  : "Connecte ton wallet MetaMask une seule fois. Tous tes ordres suivants seront exécutés automatiquement."}
              </p>

              <ol className="mb-5 space-y-2">
                {STEPS.map(({ id, label }) => {
                  const thisIdx = STEP_ORDER.indexOf(id)
                  const isActive = step === id
                  const isDone = currentIdx > thisIdx && step !== "error"

                  return (
                    <li
                      key={id}
                      className={cn(
                        "flex items-center gap-2.5 text-sm",
                        isDone ? "text-signal-yes" : isActive ? "text-ink" : "text-ink-dim",
                      )}
                    >
                      {isDone ? (
                        <CheckCircle className="h-4 w-4 shrink-0 text-signal-yes" />
                      ) : isActive ? (
                        <Loader2 className="h-4 w-4 shrink-0 animate-spin text-brand-400" />
                      ) : (
                        <span className="h-4 w-4 shrink-0 rounded-full border border-line-strong" />
                      )}
                      {label}
                    </li>
                  )
                })}
              </ol>

              {error && (
                <p
                  role="alert"
                  className="mb-4 rounded-md border border-signal-no/40 bg-signal-no/10 px-3 py-2 text-sm text-signal-no"
                >
                  {error}
                </p>
              )}

              {step === "done" ? (
                <Button variant="primary" size="lg" className="w-full" onClick={onSuccess}>
                  Continuer
                </Button>
              ) : (
                <Button
                  variant="primary"
                  size="lg"
                  className="w-full"
                  onClick={startSetup}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      {step === "connecting_wallet"
                        ? "Connexion…"
                        : step === "signing_challenge"
                          ? "Signature…"
                          : "Déploiement…"}
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <Wallet className="h-4 w-4" />
                      Connecter MetaMask
                    </span>
                  )}
                </Button>
              )}
            </motion.div>
          </FocusLock>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
