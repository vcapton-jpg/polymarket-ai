import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react"
import type { ReactNode } from "react"
import { AnimatePresence, motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { Bell, Send, X, CheckCircle2 } from "lucide-react"
import { cn } from "./utils"

/**
 * Lightweight toast system used for transient in-app alerts.
 *
 * V2.6 uses it primarily for the "Alerte Telegram envoyée" simulation
 * that fires alongside a browser notification when a position's status
 * flips to "vendre". Kept minimal on purpose — no queue management,
 * no priorities, just an auto-dismissing stack in the top-right.
 */

type ToastType = "telegram" | "info" | "success"

type Toast = {
  id: string
  type: ToastType
  title: string
  description?: string
  /** Milliseconds until auto-dismiss. Defaults to 5000. */
  duration?: number
}

type ToastContextValue = {
  toasts: Toast[]
  addToast: (toast: Omit<Toast, "id">) => string
  dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  // Timers kept in a ref so React rerenders don't leak handles. Stored per
  // id so dismissToast can cancel the auto-dismiss when the user clicks X.
  const timers = useRef<Map<string, number>>(new Map())

  const dismissToast = useCallback((id: string) => {
    const handle = timers.current.get(id)
    if (handle !== undefined) {
      window.clearTimeout(handle)
      timers.current.delete(id)
    }
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback<ToastContextValue["addToast"]>(
    (toast) => {
      const id =
        typeof crypto !== "undefined" && "randomUUID" in crypto
          ? crypto.randomUUID()
          : `toast-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const duration = toast.duration ?? 5000
      setToasts((prev) => [...prev, { ...toast, id }])
      const handle = window.setTimeout(() => dismissToast(id), duration)
      timers.current.set(id, handle)
      return id
    },
    [dismissToast],
  )

  const value = useMemo(
    () => ({ toasts, addToast, dismissToast }),
    [toasts, addToast, dismissToast],
  )

  return <ToastContext.Provider value={value}>{children}</ToastContext.Provider>
}

export function useToasts(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    throw new Error("useToasts must be used inside <ToastProvider>")
  }
  return ctx
}

export function ToastViewport() {
  // The hook will throw if the viewport is mounted outside a provider —
  // we want that to fail loudly rather than silently render nothing.
  const { toasts, dismissToast } = useToasts()

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="pointer-events-none fixed right-4 top-4 z-[60] flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2 sm:top-20 sm:right-6"
    >
      <AnimatePresence initial={false}>
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, y: -12, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
            className={cn(
              "pointer-events-auto overflow-hidden rounded-xl border bg-obsidian-850/95 p-3 pr-2 shadow-elevated backdrop-blur-xl",
              toast.type === "telegram"
                ? "border-brand-500/30"
                : toast.type === "success"
                  ? "border-signal-yes/30"
                  : "border-line-strong",
            )}
          >
            <div className="flex items-start gap-3">
              <ToastIcon type={toast.type} />
              <div className="min-w-0 flex-1">
                <p className="text-body-md font-medium text-ink">{toast.title}</p>
                {toast.description && (
                  <p className="mt-0.5 text-body-sm leading-snug text-ink-muted">
                    {toast.description}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => dismissToast(toast.id)}
                aria-label="Fermer"
                className="ml-1 inline-flex h-10 w-10 md:h-6 md:w-6 shrink-0 items-center justify-center rounded-md text-ink-dim transition-premium hover:bg-obsidian-800 hover:text-ink cursor-pointer"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

function ToastIcon({ type }: { type: ToastType }) {
  const base = "grid h-8 w-8 shrink-0 place-items-center rounded-md ring-1"
  if (type === "telegram") {
    return (
      <div className={cn(base, "bg-brand-500/15 text-brand-300 ring-brand-500/30")}>
        <Send className="h-3.5 w-3.5" aria-hidden />
      </div>
    )
  }
  if (type === "success") {
    return (
      <div className={cn(base, "bg-signal-yes/15 text-signal-yes ring-signal-yes/30")}>
        <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
      </div>
    )
  }
  return (
    <div className={cn(base, "bg-obsidian-800 text-ink-muted ring-line/60")}>
      <Bell className="h-3.5 w-3.5" aria-hidden />
    </div>
  )
}
