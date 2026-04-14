import { DIRECTION_CONFIG } from "../../lib/constants"
import { cn } from "../../lib/utils"

interface Props {
  direction: string
  animate?: boolean
}

export function DirectionBadge({ direction, animate = false }: Props) {
  const dir = DIRECTION_CONFIG[direction as keyof typeof DIRECTION_CONFIG] ?? DIRECTION_CONFIG.NEUTRAL
  const isActionable = direction === "YES" || direction === "BUY_YES" || direction === "NO" || direction === "BUY_NO"

  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wider whitespace-nowrap",
        animate && isActionable && "animate-badge-pulse",
      )}
      style={{
        color: dir.color,
        background: dir.bg,
        border: `1px solid ${dir.color}33`,
      }}
    >
      {dir.label}
    </span>
  )
}
