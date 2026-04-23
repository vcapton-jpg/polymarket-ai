type Props = {
  reasoning: string | null | undefined
  sourceTierMix: Record<string, number> | null | undefined
}

function formatTierBadge(tier: string, count: number): string {
  const tierNum = tier.replace("tier_", "")
  const label = count === 1 ? "source" : "sources"
  return `${count} ${label} Tier ${tierNum}`
}

export function WhyThisMatters({ reasoning, sourceTierMix }: Props) {
  if (!reasoning) return null
  const entries = sourceTierMix ? Object.entries(sourceTierMix).filter(([, v]) => v > 0) : []
  return (
    <section aria-label="Pourquoi ça compte" className="rounded-xl border border-border bg-card p-4 sm:p-6 mb-4">
      <header className="flex items-center gap-2 mb-2">
        <span aria-hidden>✨</span>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Pourquoi ça compte
        </h2>
      </header>
      <p className="text-base leading-relaxed">{reasoning}</p>
      {entries.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {entries.map(([tier, count]) => (
            <span key={tier} className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs">
              {formatTierBadge(tier, count)}
            </span>
          ))}
        </div>
      )}
    </section>
  )
}
