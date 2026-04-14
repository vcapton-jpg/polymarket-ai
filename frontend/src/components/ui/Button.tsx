import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost"
  size?: "sm" | "md" | "lg"
  icon?: ReactNode
}

const variants: Record<string, string> = {
  primary: "bg-accent text-surface-0 hover:brightness-110 shadow-card",
  secondary: "bg-surface-card text-txt-secondary shadow-card hover:text-accent",
  ghost: "bg-transparent text-txt-muted hover:text-txt-secondary hover:bg-surface-raised",
}

const sizes: Record<string, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  children,
  className,
  ...rest
}: Props) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-all duration-150",
        variants[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {children}
      {icon}
    </button>
  )
}
