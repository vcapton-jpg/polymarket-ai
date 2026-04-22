import { useEffect, useLayoutEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import { X } from "lucide-react"
import { useMotionConfig } from "@/lib/motion"
import { cn } from "@/lib/utils"

type Rect = { top: number; left: number; width: number; height: number }

type CoachMarkProps = {
  /** DOM id of the target element. The overlay positions via getBoundingClientRect. */
  targetId: string
  /** Tooltip copy. */
  message: string
  /** Whether the overlay is visible. */
  open: boolean
  /** Called when the user dismisses (X, Escape, or clicks the target). */
  onDismiss: () => void
  /** Preferred placement. Defaults to "bottom". */
  placement?: "top" | "bottom"
  /** Max milliseconds to show the ring pulse. Defaults to 5000. */
  pulseMs?: number
}

/**
 * Reusable coach-mark overlay. Points at a target element via its DOM id
 * with a tooltip bubble and a subtle brand-glow ring. The target element
 * doesn't need to be modified — we position absolutely using
 * `getBoundingClientRect`.
 *
 * Respects `prefers-reduced-motion`.
 */
export function CoachMark({
  targetId,
  message,
  open,
  onDismiss,
  placement = "bottom",
  pulseMs = 5000,
}: CoachMarkProps) {
  const [rect, setRect] = useState<Rect | null>(null)
  const [pulsing, setPulsing] = useState(true)
  const reduced = useReducedMotion()
  const motionConfig = useMotionConfig("default")
  const closeBtnRef = useRef<HTMLButtonElement>(null)

  // Focus the close button when opened so keyboard users can immediately
  // dismiss with Enter/Space.
  useEffect(() => {
    if (!open) return
    // Small delay to let the portal + animation mount.
    const t = window.setTimeout(() => closeBtnRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [open])

  // Resolve target rect once opened; recompute on resize/scroll.
  useLayoutEffect(() => {
    if (!open || typeof window === "undefined") return
    const update = () => {
      const el = document.getElementById(targetId)
      if (!el) {
        setRect(null)
        return
      }
      const r = el.getBoundingClientRect()
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    update()
    // Retry shortly in case the target just mounted.
    const t = window.setTimeout(update, 60)
    window.addEventListener("resize", update)
    window.addEventListener("scroll", update, true)
    return () => {
      window.clearTimeout(t)
      window.removeEventListener("resize", update)
      window.removeEventListener("scroll", update, true)
    }
  }, [open, targetId])

  // Auto-stop the ring pulse after pulseMs.
  useEffect(() => {
    if (!open) return
    setPulsing(true)
    const t = window.setTimeout(() => setPulsing(false), pulseMs)
    return () => window.clearTimeout(t)
  }, [open, pulseMs])

  // Dismiss on Escape; also dismiss on target click.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss()
    }
    const el = document.getElementById(targetId)
    const onTargetClick = () => onDismiss()
    window.addEventListener("keydown", onKey)
    el?.addEventListener("click", onTargetClick, { capture: true })
    return () => {
      window.removeEventListener("keydown", onKey)
      el?.removeEventListener("click", onTargetClick, { capture: true } as EventListenerOptions)
    }
  }, [open, onDismiss, targetId])

  if (!open || !rect || typeof document === "undefined") return null

  const ringPadding = 6
  const ringTop = rect.top - ringPadding
  const ringLeft = rect.left - ringPadding
  const ringWidth = rect.width + ringPadding * 2
  const ringHeight = rect.height + ringPadding * 2

  const bubbleMaxWidth = Math.min(340, Math.max(240, rect.width))
  const bubbleTop =
    placement === "bottom"
      ? ringTop + ringHeight + 10
      : ringTop - 12 /* subtract bubble height via transform */
  const bubbleLeft = Math.max(12, ringLeft)

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="coachmark-root"
        className="pointer-events-none fixed inset-0 z-[60]"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={motionConfig}
        aria-hidden={false}
      >
        {/* Subtle dim */}
        <div role="presentation" className="absolute inset-0 bg-obsidian-950/40" />

        {/* Ring on target */}
        <motion.div
          className={cn(
            "absolute rounded-2xl border-2 border-brand-400/70",
            "shadow-[0_0_0_6px_rgba(11,224,166,0.08),0_0_40px_rgba(11,224,166,0.35)]",
            pulsing && !reduced && "animate-pulse",
          )}
          style={{
            top: ringTop,
            left: ringLeft,
            width: ringWidth,
            height: ringHeight,
          }}
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={motionConfig}
        />

        {/* Tooltip bubble */}
        <motion.div
          role="dialog"
          aria-label="Astuce"
          className="pointer-events-auto absolute rounded-xl border border-brand-500/40 bg-obsidian-850/95 p-4 shadow-elevated backdrop-blur-xl"
          style={{
            top: bubbleTop,
            left: bubbleLeft,
            maxWidth: bubbleMaxWidth,
            transform: placement === "top" ? "translateY(-100%)" : undefined,
          }}
          initial={{ opacity: 0, scale: 0.96, y: placement === "bottom" ? -6 : 6 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={motionConfig}
        >
          <button
            ref={closeBtnRef}
            type="button"
            onClick={onDismiss}
            aria-label="Fermer l’astuce"
            className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-md text-ink-dim hover:text-ink hover:bg-obsidian-800 cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
          <p className="pr-7 text-body-sm text-ink">{message}</p>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  )
}
