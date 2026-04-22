import { useId, useState } from "react"
import { Info } from "lucide-react"
import { cn } from "@/lib/utils"

type InfoTooltipProps = {
  /** Tooltip copy, shown on hover/focus. */
  message: string
  /** Accessible label for the trigger. Defaults to "Plus d’informations". */
  label?: string
  className?: string
}

/**
 * Minimal info-tooltip: an `Info` icon trigger that reveals an
 * absolutely-positioned bubble on hover or focus. Keyboard-accessible
 * (focusable button, `role="tooltip"` on the bubble, `aria-describedby`
 * wired to the trigger).
 */
export function InfoTooltip({ message, label = "Plus d’informations", className }: InfoTooltipProps) {
  const [open, setOpen] = useState(false)
  const tipId = useId()

  return (
    <span className={cn("relative inline-flex items-center align-middle", className)}>
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? tipId : undefined}
        tabIndex={0}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setOpen(false)
        }}
        className="inline-grid h-4 w-4 place-items-center rounded-full text-ink-dim hover:text-brand-400 focus:outline-none focus-visible:text-brand-400 focus-visible:ring-2 focus-visible:ring-brand-500/40 cursor-help"
      >
        <Info className="h-3 w-3" aria-hidden />
      </button>
      {open && (
        <span
          id={tipId}
          role="tooltip"
          className="absolute bottom-full left-1/2 z-40 mb-1.5 w-max max-w-[240px] -translate-x-1/2 rounded-md border border-line-strong bg-obsidian-850 px-2.5 py-1.5 text-label-sm leading-snug text-ink shadow-elevated"
        >
          {message}
        </span>
      )}
    </span>
  )
}
