import { DIRECTION_CONFIG } from "../../lib/constants"
import { cn } from "../../lib/utils"

interface Props {
  direction: string
  animate?: boolean
}

function glowForDirection(direction: string): string | undefined {
  if (direction === "BUY_YES" || direction === "YES") {
    return "0 0 14px rgba(16,185,129,0.28), 0 0 1px rgba(16,185,129,0.4)"
  }
  if (direction === "BUY_NO" || direction === "NO") {
    return "0 0 14px rgba(239,68,68,0.28), 0 0 1px rgba(239,68,68,0.4)"
  }
  return undefined
}

export function DirectionBadge({ direction, animate = false }: Props) {
  const dir = DIRECTION_CONFIG[direction as keyof typeof DIRECTION_CONFIG] ?? DIRECTION_CONFIG.NEUTRAL
  const isActionable = direction === "YES" || direction === "BUY_YES" || direction === "NO" || direction === "BUY_NO"
  const glow = isActionable ? glowForDirection(direction) : undefined

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-bold uppercase tracking-wider whitespace-nowrap",
        animate && isActionable && "animate-badge-pulse",
      )}
      style={{
        color: dir.color,
        background: dir.bg,
        border: `1px solid ${dir.color}40`,
        boxShadow: glow,
      }}
    >
      {dir.label}
    </span>
  )
}
