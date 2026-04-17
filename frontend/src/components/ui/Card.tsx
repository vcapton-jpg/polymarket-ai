import type { CSSProperties, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props {
  children: ReactNode
  className?: string
  style?: CSSProperties
}

export function Card({ children, className, style }: Props) {
  return (
    <div
      className={cn(
        "glass-card glass-card-hover rounded-xl border border-edge-subtle shadow-inner-glow",
        "p-5 md:p-6",
        "transition-all duration-300 ease-out",
        className,
      )}
      style={style}
    >
      {children}
    </div>
  )
}
