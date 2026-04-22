import { Lock } from "lucide-react"

/**
 * Tiny chip flagging that a feature is reserved to a paid plan.
 *
 * Purely informational — the containing control remains clickable. Apply
 * next to a heading, toggle label, or filter pill to signal the gate
 * without blocking interaction.
 */
export function PaywallChip({ plan = "pro" }: { plan?: "pro" | "api" }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md bg-brand-500/10 px-1.5 py-0.5 text-label-xs font-medium text-brand-400">
      <Lock size={10} />
      {plan === "pro" ? "Pro" : "API"}
    </span>
  )
}
