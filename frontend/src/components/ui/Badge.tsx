import type { CSSProperties, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props {
  children?: ReactNode
  label?: string
  color?: string
  bg?: string
  size?: "sm" | "md"
  style?: CSSProperties
}

export function Badge({ children, label, color, bg, size = "sm", style }: Props) {
  const pad = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-[11px]"
  const baseColor = color ?? "#8892A4"

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md font-semibold uppercase tracking-wider whitespace-nowrap",
        "backdrop-blur-md backdrop-saturate-150",
        pad,
      )}
      style={{
        color: baseColor,
        background: bg ?? `${baseColor}14`,
        border: `1px solid ${baseColor}26`,
        ...style,
      }}
    >
      {children ?? label}
    </span>
  )
}
