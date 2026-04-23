import { Star } from "lucide-react"

type Props = { xp: number; level: number }

/**
 * Compact level + XP readout. Rendered inline near the Portfolio header
 * so users see their learning progression without it dominating the page.
 */
export function XPBadge({ xp, level }: Props) {
  return (
    <div
      className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs text-brand-200"
      aria-label={`Niveau ${level}, ${xp} points d'expérience`}
    >
      <Star className="h-3.5 w-3.5 text-brand-400" aria-hidden="true" />
      <span className="font-semibold">{`Niv. ${level}`}</span>
      <span className="text-brand-300/80">{`· ${xp} XP`}</span>
    </div>
  )
}
