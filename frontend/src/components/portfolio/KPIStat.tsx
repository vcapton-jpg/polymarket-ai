import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"

type KPIStatProps = {
  label: string
  value: number
  suffix?: string
  prefix?: string
  tone?: "neutral" | "positive" | "negative" | "brand"
  decimals?: number
  sub?: string
  icon?: React.ReactNode
  className?: string
  /**
   * Optional formatter for the animated value. If provided, it replaces the
   * default locale-based formatting AND the prefix/suffix combo — use it
   * when you need currency-aware animation (e.g. formatMoney from
   * useUserPreferences). The formatter receives the live count-up value.
   */
  format?: (n: number) => string
}

export function KPIStat({
  label,
  value,
  suffix,
  prefix,
  tone = "neutral",
  decimals = 0,
  sub,
  icon,
  className,
  format,
}: KPIStatProps) {
  const display = useCountUp(value, 900, decimals, format)

  const toneCls =
    tone === "positive"
      ? "text-signal-yes"
      : tone === "negative"
        ? "text-signal-no"
        : tone === "brand"
          ? "text-brand-300"
          : "text-ink"

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className={cn(
        "relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm px-5 py-4",
        className,
      )}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-label-xs font-mono uppercase tracking-[0.14em] text-ink-dim">
          {label}
        </span>
        {icon && <span className="text-ink-dim">{icon}</span>}
      </div>
      <div className={cn("num font-display text-[1.75rem] font-semibold leading-none tracking-tight", toneCls)}>
        {format ? (
          display
        ) : (
          <>
            {prefix}
            {display}
            {suffix}
          </>
        )}
      </div>
      {sub && (
        <div className="mt-2 text-label-sm text-ink-muted">{sub}</div>
      )}
    </motion.div>
  )
}

function useCountUp(
  target: number,
  durationMs = 800,
  decimals = 0,
  format?: (n: number) => string,
): string {
  const [val, setVal] = useState(0)

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches
    if (reduced) {
      setVal(target)
      return
    }

    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      setVal(target * eased)
      if (t < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs])

  if (format) return format(val)

  const sign = val < 0 ? "−" : ""
  const abs = Math.abs(val)
  return sign + abs.toLocaleString("fr-FR", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}
