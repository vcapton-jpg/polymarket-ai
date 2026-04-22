import { motion } from "framer-motion"
import { cn } from "@/lib/utils"
import { statusFromLifePercent } from "@/lib/useLifeDecay"
import { useMotionConfig } from "@/lib/motion"
import type { PositionStatus } from "@/types/signal"

type LifeBarProps = {
  percent: number
  className?: string
  showLabel?: boolean
  flash?: boolean
}

const STATUS_META: Record<
  PositionStatus,
  { label: string; dotCls: string; textCls: string; fillCls: string }
> = {
  tenir: {
    label: "Tenir",
    dotCls: "bg-signal-yes",
    textCls: "text-signal-yes",
    fillCls: "bg-gradient-to-r from-signal-yes via-signal-yes/90 to-signal-yes/70",
  },
  surveiller: {
    label: "Surveiller",
    dotCls: "bg-signal-amber",
    textCls: "text-signal-amber",
    fillCls: "bg-gradient-to-r from-signal-amber via-signal-amber/90 to-signal-amber/70",
  },
  vendre: {
    label: "Vendre",
    dotCls: "bg-signal-no",
    textCls: "text-signal-no",
    fillCls: "bg-gradient-to-r from-signal-no via-signal-no/90 to-signal-no/70",
  },
}

export function LifeBar({ percent, className, showLabel = true, flash = false }: LifeBarProps) {
  const clamped = Math.max(0, Math.min(100, percent))
  const status = statusFromLifePercent(clamped)
  const meta = STATUS_META[status]
  const motionConfig = useMotionConfig("default")

  return (
    <div className={cn("flex flex-col gap-2", className, flash && "animate-flash motion-reduce:animate-none")}>
      <div className="flex items-center justify-between gap-3">
        <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-line/70">
          <motion.div
            role="progressbar"
            aria-valuenow={Math.round(clamped)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Barre de vie du signal"
            className={cn("h-full rounded-full", meta.fillCls)}
            initial={false}
            animate={{ width: `${clamped}%` }}
            transition={motionConfig}
          />
        </div>
        <span className="num tabular-nums text-label-sm font-semibold text-ink w-10 text-right">
          {Math.round(clamped)}%
        </span>
      </div>
      {showLabel && (
        <div className="flex items-center gap-1.5 text-label-sm">
          <span className={cn("relative inline-flex h-1.5 w-1.5")}>
            <span className={cn("absolute inset-0 animate-ping motion-reduce:animate-none rounded-full opacity-60", meta.dotCls)} />
            <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", meta.dotCls)} />
          </span>
          <span className={cn("font-medium", meta.textCls)}>{meta.label}</span>
        </div>
      )}
    </div>
  )
}

export function statusAccentClass(status: PositionStatus): string {
  return {
    tenir: "border-line-strong",
    surveiller: "border-signal-amber/30",
    vendre: "border-signal-no/40 bg-signal-no/[0.03]",
  }[status]
}
