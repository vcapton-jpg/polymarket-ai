import { forwardRef, type InputHTMLAttributes } from "react"
import { cn } from "@/lib/utils"

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = "text", ...props }, ref) => {
    return (
      <input
        ref={ref}
        type={type}
        className={cn(
          "flex h-11 w-full rounded-md border border-line-strong bg-obsidian-800 px-3.5 py-2 text-sm text-ink",
          "placeholder:text-ink-dim",
          "transition-premium",
          "focus-visible:outline-none focus-visible:border-brand-500/60 focus-visible:ring-2 focus-visible:ring-brand-500/20 focus-visible:ring-offset-0",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
    )
  },
)
Input.displayName = "Input"
