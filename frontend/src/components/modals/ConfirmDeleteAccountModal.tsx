import { useCallback, useEffect } from "react"
import { AnimatePresence, motion } from "framer-motion"
import FocusLock from "react-focus-lock"
import { X } from "lucide-react"
import { useMotionConfig } from "@/lib/motion"

type ConfirmDeleteAccountModalProps = {
  open: boolean
  onClose: () => void
  onConfirm: () => void
}

/**
 * Final confirmation before wiping the user's account. Mirrors the
 * EndOfTrialModal a11y pattern: FocusLock, role=dialog, aria-modal,
 * aria-labelledby, Escape-to-close, click-backdrop-to-close.
 */
export default function ConfirmDeleteAccountModal({
  open,
  onClose,
  onConfirm,
}: ConfirmDeleteAccountModalProps) {
  const motionConfig = useMotionConfig("default")

  const close = useCallback(() => {
    onClose()
  }, [onClose])

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
          key="confirm-delete-backdrop"
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
              aria-labelledby="confirm-delete-title"
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

              <p className="mb-2 font-mono text-label-xs uppercase tracking-[0.14em] text-signal-no">
                Zone danger
              </p>
              <h2
                id="confirm-delete-title"
                className="font-display text-title-md font-semibold tracking-tight text-ink md:text-[1.5rem]"
              >
                {"Supprimer définitivement ton compte\u00A0?"}
              </h2>
              <p className="mt-3 text-body-md leading-relaxed text-ink-muted">
                Cette action est irréversible. Toutes tes positions et ton historique seront perdus.
              </p>

              <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={close}
                  className="inline-flex h-11 items-center justify-center rounded-md border border-line-strong bg-obsidian-850 px-4 text-body-md font-medium text-ink transition-premium hover:border-brand-500/40 hover:bg-obsidian-700 cursor-pointer"
                >
                  Annuler
                </button>
                <button
                  type="button"
                  onClick={onConfirm}
                  className="inline-flex h-11 items-center justify-center rounded-md bg-signal-no px-4 text-body-md font-semibold text-white transition-premium hover:bg-signal-no/90 cursor-pointer"
                >
                  Supprimer définitivement
                </button>
              </div>
            </motion.div>
          </FocusLock>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
