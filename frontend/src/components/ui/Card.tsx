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
        "bg-surface-card rounded-lg shadow-card p-5 md:p-6",
        className,
      )}
      style={style}
    >
      {children}
    </div>
  )
}
