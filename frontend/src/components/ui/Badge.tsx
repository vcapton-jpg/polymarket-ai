import type { CSSProperties, ReactNode } from "react"

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

  return (
    <span
      className={`inline-flex items-center rounded ${pad} font-semibold uppercase tracking-wider whitespace-nowrap`}
      style={{
        color: color ?? "#94A3B8",
        background: bg ?? `${color ?? "#94A3B8"}1A`,
        border: `1px solid ${color ?? "#94A3B8"}22`,
        ...style,
      }}
    >
      {children ?? label}
    </span>
  )
}
