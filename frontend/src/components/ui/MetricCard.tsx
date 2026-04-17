import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  useMotionValue,
  useMotionValueEvent,
  useSpring,
} from "framer-motion"
import { cn } from "../../lib/utils"

interface Props {
  label: string
  value: string | number
  sub?: string
  icon?: ReactNode
  mono?: boolean
}

function parseNumericValue(value: string | number): { num: number; decimals: number } | null {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null
    const str = String(value)
    const decimals = str.includes(".") ? Math.min(str.split(".")[1]?.length ?? 0, 4) : 0
    return { num: value, decimals }
  }
  const trimmed = value.trim()
  if (!trimmed) return null
  const normalized = trimmed.replace(/,/g, "")
  const num = Number(normalized)
  if (Number.isNaN(num)) return null
  const decimals = normalized.includes(".")
    ? Math.min(normalized.split(".")[1]?.length ?? 0, 4)
    : 0
  return { num, decimals }
}

function MetricValueBody({
  value,
  mono,
}: {
  value: string | number
  mono?: boolean
}) {
  const parsed = useMemo(() => parseNumericValue(value), [value])
  const target = useMotionValue(0)
  const spring = useSpring(target, { stiffness: 120, damping: 28, mass: 0.6 })
  const [text, setText] = useState("0")

  useEffect(() => {
    if (!parsed) return
    target.set(parsed.num)
  }, [parsed, target])

  useMotionValueEvent(spring, "change", (v) => {
    if (!parsed) return
    if (parsed.decimals > 0) {
      setText(v.toFixed(parsed.decimals))
    } else {
      setText(String(Math.round(v)))
    }
  })

  if (!parsed) {
    return (
      <div
        className={`text-2xl font-bold text-txt-primary leading-tight mb-1 tracking-tight ${mono ? "font-mono font-tabular" : "font-display"}`}
      >
        {value}
      </div>
    )
  }

  return (
    <div
      className={`text-2xl font-bold text-txt-primary leading-tight mb-1 tracking-tight ${mono ? "font-mono font-tabular" : "font-display"}`}
    >
      {text}
    </div>
  )
}

export function MetricCard({ label, value, sub, icon, mono }: Props) {
  return (
    <div
      className={cn(
        "glass-card glass-card-hover rounded-xl border border-edge-subtle shadow-inner-glow",
        "p-4 md:p-5",
        "transition-all duration-300 ease-out",
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <span className="text-[11px] font-semibold text-txt-muted uppercase tracking-widest">
          {label}
        </span>
        {icon && (
          <div className="w-9 h-9 flex items-center justify-center rounded-lg glass-card border border-edge-subtle shadow-glass text-accent">
            {icon}
          </div>
        )}
      </div>
      <MetricValueBody value={value} mono={mono} />
      {sub && (
        <span className="text-xs text-txt-muted leading-relaxed">{sub}</span>
      )}
    </div>
  )
}
