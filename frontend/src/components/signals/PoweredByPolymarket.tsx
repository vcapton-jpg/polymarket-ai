import { cn } from "@/lib/utils"

type PoweredByPolymarketProps = {
  className?: string
  /** Visual size — `xs` used inline, `sm` standard in forms, `md` stands alone. */
  size?: "xs" | "sm" | "md"
  /** Optional href — defaults to polymarket.com. */
  href?: string
}

/**
 * Builder Program compliance badge. Foresight surfaces signals but execution
 * happens on Polymarket infrastructure — this badge credits the venue.
 *
 * Intentionally discreet: small text, subtle border, Polymarket purple accent.
 * It's attribution, not a brand takeover.
 */
export function PoweredByPolymarket({
  className,
  size = "sm",
  href = "https://polymarket.com",
}: PoweredByPolymarketProps) {
  const sizeCls = {
    xs: "px-1.5 py-0.5 text-[0.625rem] gap-1",
    sm: "px-2 py-0.5 text-label-xs gap-1.5",
    md: "px-2.5 py-1 text-label-xs gap-1.5",
  }[size]

  const dotCls = {
    xs: "h-1 w-1",
    sm: "h-1.5 w-1.5",
    md: "h-1.5 w-1.5",
  }[size]

  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className={cn(
        "inline-flex w-fit items-center rounded-full border border-line/70 bg-obsidian-800/40",
        "font-medium text-ink-dim hover:text-ink hover:border-line-strong",
        "transition-premium",
        sizeCls,
        className,
      )}
      aria-label="Partenaire Polymarket"
    >
      {/* Polymarket logo mark */}
      <svg
        viewBox="0 0 20 20"
        fill="none"
        aria-hidden
        className={cn("shrink-0", dotCls === "h-1 w-1" ? "h-3 w-3" : dotCls === "h-1.5 w-1.5" ? "h-3.5 w-3.5" : "h-4 w-4")}
      >
        <rect width="20" height="20" rx="4" fill="#1652F0" />
        <path d="M5.5 5h5.25C12.99 5 14.5 6.51 14.5 8.25S12.99 11.5 11.5 11.5H9V15H5.5V5z" fill="white" />
      </svg>
      <span className="leading-none">Partenaire Polymarket</span>
    </a>
  )
}
