import { useCallback, useEffect } from "react"
import { AnimatePresence, motion } from "framer-motion"
import FocusLock from "react-focus-lock"
import { Pause } from "lucide-react"
import { useMotionConfig } from "@/lib/motion"

type CooloffModalProps = {
  open: boolean
  cooloffUntil: string | null
  onClose: () => void
}

/**
 * Full-screen explainer shown once when the user hits the cooloff gate
 * (3 consecutive losing real trades → 24h forced pause). Meant to frame
 * the pause as protective, not punitive. Dismiss is the only action;
 * the cooloff itself is enforced server-side regardless of this modal.
 */
export default function CooloffModal({
  open,
  cooloffUntil,
  onClose,
}: CooloffModalProps) {
  const motionConfig = useMotionConfig("default")

  const close = useCallback(() => onClose(), [onClose])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, close])

  const untilLabel = cooloffUntil
    ? new Date(cooloffUntil).toLocaleString("fr-FR", {
        weekday: "long",
        day: "2-digit",
        month: "long",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="cooloff-backdrop"
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
              aria-labelledby="cooloff-title"
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.98 }}
              transition={motionConfig}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-md overflow-hidden rounded-2xl border border-line-strong bg-obsidian-800 p-6 shadow-elevated md:p-7"
            >
              <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-signal-no/15 px-3 py-1 font-mono text-label-xs uppercase tracking-[0.14em] text-signal-no">
                <Pause className="h-3 w-3" aria-hidden="true" />
                Pause de 24h
              </div>
              <h2
                id="cooloff-title"
                className="font-display text-title-md font-semibold tracking-tight text-ink md:text-[1.5rem]"
              >
                {"On marque une pause\u00A0—\u00A0c'est normal."}
              </h2>
              <p className="mt-3 text-body-md leading-relaxed text-ink-muted">
                Tu viens d'enchaîner 3 pertes réelles. Pour protéger ton budget
                et ta lucidité, le trading réel est suspendu pendant 24h. Tu
                peux toujours consulter les signaux et t'entraîner en mode
                papier pendant ce temps.
              </p>
              {untilLabel && (
                <p className="mt-3 rounded-md border border-line/60 bg-obsidian-850 px-3 py-2 text-sm text-ink">
                  {`Reprise possible : ${untilLabel}`}
                </p>
              )}
              <p className="mt-4 text-xs text-ink-dim">
                Cette pause est appliquée côté serveur et ne peut pas être
                désactivée. Tu fais bien de t'en tenir à tes limites.
              </p>

              <div className="mt-6 flex justify-end">
                <button
                  type="button"
                  onClick={close}
                  className="inline-flex h-11 items-center justify-center rounded-md bg-brand-500 px-5 text-body-md font-semibold text-obsidian-950 transition-premium hover:bg-brand-400 cursor-pointer"
                >
                  J'ai compris
                </button>
              </div>
            </motion.div>
          </FocusLock>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
