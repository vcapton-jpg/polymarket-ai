import type { ButtonHTMLAttributes, ReactNode } from "react"
import { cn } from "../../lib/utils"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
  icon?: ReactNode
  isLoading?: boolean
}

const variants: Record<string, string> = {
  primary:
    "bg-gradient-gold text-surface-0 shadow-glow hover:shadow-glow-lg hover:brightness-[1.03] active:brightness-95 border border-accent/20",
  secondary:
    "glass-card border border-edge-subtle text-txt-secondary shadow-glass hover:text-accent hover:border-edge-accent/30 hover:shadow-card-hover",
  ghost:
    "bg-transparent text-txt-muted hover:text-txt-secondary hover:bg-surface-hover/80 border border-transparent",
  danger:
    "bg-danger/15 text-danger border border-danger/20 hover:bg-danger/25 shadow-card hover:shadow-card-hover",
}

const sizes: Record<string, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-6 py-3 text-base",
}

function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-[1em] w-[1em] shrink-0 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
      />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

export function Button({
  variant = "primary",
  size = "md",
  icon,
  children,
  className,
  isLoading = false,
  disabled,
  ...rest
}: Props) {
  const isDisabled = disabled || isLoading

  return (
    <button
      type="button"
      disabled={isDisabled}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-all duration-150",
        "disabled:pointer-events-none disabled:opacity-50",
        variants[variant],
        sizes[size],
        isLoading && "relative",
        className,
      )}
      aria-busy={isLoading || undefined}
      {...rest}
    >
      {isLoading && <Spinner />}
      <span className={cn("inline-flex items-center gap-2", isLoading && "opacity-90")}>
        {children}
        {!isLoading && icon}
      </span>
    </button>
  )
}
