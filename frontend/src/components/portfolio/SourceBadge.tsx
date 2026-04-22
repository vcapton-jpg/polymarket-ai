import { Sparkles, PenLine } from "lucide-react"
import type { PositionSource } from "@/types/signal"
import { cn } from "@/lib/utils"

type SourceBadgeProps = {
  source: PositionSource
  size?: "xs" | "sm"
  className?: string
}

/**
 * Discreet badge showing whether a position was opened natively via the
 * Foresight OrderForm (Builder Program) or logged manually after trading
 * directly on Polymarket.
 */
export function SourceBadge({ source, size = "sm", className }: SourceBadgeProps) {
  const isNative = source === "native"

  const sizeCls = {
    xs: "h-5 px-1.5 text-[0.625rem] gap-1",
    sm: "h-6 px-2 text-label-xs gap-1.5",
  }[size]

  const iconCls = size === "xs" ? "h-2.5 w-2.5" : "h-3 w-3"

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border font-mono uppercase tracking-wider",
        sizeCls,
        isNative
          ? "border-brand-500/40 bg-brand-500/10 text-brand-300"
          : "border-line bg-obsidian-800/60 text-ink-muted",
        className,
      )}
      title={isNative ? "Position ouverte via Foresight" : "Position saisie manuellement"}
    >
      {isNative ? (
        <Sparkles className={iconCls} aria-hidden />
      ) : (
        <PenLine className={iconCls} aria-hidden />
      )}
      {isNative ? "Native" : "Manuel"}
    </span>
  )
}
