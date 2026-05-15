type Props = {
  reasoning: string | null | undefined
  sourceTierMix: Record<string, number> | null | undefined
}

function formatTierBadge(tier: string, count: number): string {
  const tierNum = tier.replace("tier_", "")
  const label = count === 1 ? "source" : "sources"
  return `${count} ${label} Tier ${tierNum}`
}

/**
 * The v2 ImpactAnalyzer prompt forces a machine-auditable pin sentence
 * at the end of `reasoning`:
 *
 *   "Market at 0.6400, my estimate 0.80, so BUY_YES with strength 0.6."
 *
 * It's there so WE can audit calls without re-reading JSON — but it
 * leaks raw to the end user (UX feedback 2026-05-13: "il faut du texte,
 * pas juste qu'elle dise qu'elle est"). This splits the prose from the
 * pin: the prose renders as-is, the pin becomes a clean FR data strip.
 */
const PIN_RE =
  /\s*Market at\s*([\d.]+)\s*,?\s*my estimate\s*([\d.]+)\s*,?\s*so\s*([A-Z_]+)(?:\s+with strength\s*([\d.]+))?\.?\s*$/i

type ParsedPin = {
  prose: string
  marketPct: number
  estimatePct: number
  direction: string
  edgePts: number
}

export function parseReasoning(raw: string): { prose: string; pin: ParsedPin | null } {
  const m = raw.match(PIN_RE)
  if (!m) return { prose: raw.trim(), pin: null }
  const market = parseFloat(m[1])
  const estimate = parseFloat(m[2])
  if (Number.isNaN(market) || Number.isNaN(estimate)) {
    return { prose: raw.trim(), pin: null }
  }
  const dirRaw = (m[3] || "").toUpperCase()
  const direction =
    dirRaw === "BUY_YES" || dirRaw === "YES"
      ? "BUY YES"
      : dirRaw === "BUY_NO" || dirRaw === "NO"
        ? "BUY NO"
        : dirRaw === "NEUTRAL"
          ? "NEUTRE"
          : dirRaw
  return {
    prose: raw.replace(PIN_RE, "").trim(),
    pin: {
      prose: raw.replace(PIN_RE, "").trim(),
      marketPct: Math.round(market * 100),
      estimatePct: Math.round(estimate * 100),
      direction,
      edgePts: Math.round((estimate - market) * 100),
    },
  }
}

export function WhyThisMatters({ reasoning, sourceTierMix }: Props) {
  if (!reasoning) return null
  const { prose, pin } = parseReasoning(reasoning)
  const entries = sourceTierMix ? Object.entries(sourceTierMix).filter(([, v]) => v > 0) : []
  return (
    <section aria-label="Pourquoi ça compte" className="rounded-xl border border-border bg-card p-4 sm:p-6 mb-4">
      <header className="flex items-center gap-2 mb-2">
        <span aria-hidden>✨</span>
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Pourquoi ça compte
        </h2>
      </header>

      {prose && <p className="text-base leading-relaxed">{prose}</p>}

      {pin && (
        <div className="mt-3 grid grid-cols-3 gap-2 rounded-lg border border-border bg-muted/40 p-3 text-center">
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Marché</div>
            <div className="num text-lg font-semibold">{pin.marketPct} %</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Notre estimation</div>
            <div className="num text-lg font-semibold">{pin.estimatePct} %</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-wide text-muted-foreground">Écart</div>
            <div
              className={
                "num text-lg font-semibold " +
                (pin.edgePts > 0
                  ? "text-signal-yes"
                  : pin.edgePts < 0
                    ? "text-signal-no"
                    : "")
              }
            >
              {pin.edgePts > 0 ? "+" : ""}
              {pin.edgePts} pts
            </div>
          </div>
          <p className="col-span-3 mt-1 text-sm text-muted-foreground">
            Le marché évalue ce résultat à <strong>{pin.marketPct}&nbsp;%</strong>. Notre
            analyse l'estime à <strong>{pin.estimatePct}&nbsp;%</strong> — un écart de{" "}
            <strong>
              {pin.edgePts > 0 ? "+" : ""}
              {pin.edgePts} points
            </strong>{" "}
            qui oriente vers <strong>{pin.direction}</strong>.
          </p>
        </div>
      )}

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
