import { useCallback, useEffect, useState } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { useNavigate } from "react-router-dom"
import FocusLock from "react-focus-lock"
import { X } from "lucide-react"
import { useMotionConfig } from "@/lib/motion"
import { checkAndHandleTrialExpiry } from "@/lib/trial"
import { SESSION_KEYS } from "@/lib/storageKeys"

const SESSION_FLAG = SESSION_KEYS.trialExpiryShown

function wasShownThisSession(): boolean {
  try {
    return sessionStorage.getItem(SESSION_FLAG) === "1"
  } catch {
    return false
  }
}

function markShownThisSession(): void {
  try {
    sessionStorage.setItem(SESSION_FLAG, "1")
  } catch {
    // ignore
  }
}

export default function EndOfTrialModal() {
  const navigate = useNavigate()
  const motionConfig = useMotionConfig("default")
  const [open, setOpen] = useState(false)

  useEffect(() => {
    if (wasShownThisSession()) return
    const { expired } = checkAndHandleTrialExpiry()
    if (expired) setOpen(true)
  }, [])

  // Stable close identity so the keydown effect doesn't re-bind on every
  // render. Matters when we later add other effects that close-on-unmount.
  const close = useCallback(() => {
    markShownThisSession()
    setOpen(false)
  }, [])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, close])

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="end-trial-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={motionConfig}
          className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm"
          onClick={close}
        >
          <FocusLock returnFocus>
            <motion.div
              role="dialog"
              aria-modal="true"
              aria-labelledby="end-trial-title"
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={motionConfig}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-md overflow-hidden rounded-2xl border border-line-strong bg-obsidian-800 p-6 shadow-elevated md:p-7"
            >
              <button
                type="button"
                onClick={close}
                aria-label="Fermer"
                className="absolute right-3 top-3 inline-flex h-10 w-10 md:h-8 md:w-8 items-center justify-center rounded-md text-ink-dim transition-premium hover:bg-obsidian-700 hover:text-ink cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>

              <p className="mb-2 font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
                Fin de l{"\u2019"}essai
              </p>
              <h2
                id="end-trial-title"
                className="font-display text-title-md font-semibold tracking-tight text-ink md:text-[1.5rem]"
              >
                {"Ton\u00A0essai Pro est\u00A0terminé"}
              </h2>
              <p className="mt-3 text-body-md leading-relaxed text-ink-muted">
                Tu es automatiquement passé en Free. Tu gardes tes signaux actifs et ton
                historique des 30 derniers jours.
              </p>

              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => {
                    close()
                    navigate("/pricing")
                  }}
                  className="inline-flex h-11 items-center justify-center rounded-md border border-line-strong bg-obsidian-850 px-4 text-body-md font-medium text-ink transition-premium hover:border-brand-500/40 hover:bg-obsidian-700 cursor-pointer"
                >
                  Voir ce que tu perds
                </button>
                <button
                  type="button"
                  onClick={() => {
                    close()
                    navigate("/pricing?plan=pro")
                  }}
                  className="inline-flex h-11 items-center justify-center rounded-md bg-brand-500 px-4 text-body-md font-semibold text-obsidian-950 transition-premium hover:bg-brand-400 cursor-pointer"
                >
                  {"Passer Pro — 29\u00A0€/mois"}
                </button>
              </div>
            </motion.div>
          </FocusLock>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
