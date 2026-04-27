import { formatDistanceToNow } from "date-fns"
import { fr } from "date-fns/locale"
import type { SignalSource } from "@/types/signal"

type Props = { sources: SignalSource[] }

// Dark-theme tier badges — light Tailwind defaults (bg-green-100, bg-amber-100,
// bg-gray-100) rendered nearly invisible on the obsidian background. We use
// the project's signal palette + tinted fills + 1px tone-matched borders so
// the badge is legible at a glance and the tier ranking reads from color
// alone (T1 green / T2 amber / T3 muted).
const tierBadgeClass: Record<1 | 2 | 3, string> = {
  1: "bg-signal-yes/15 text-signal-yes border border-signal-yes/30",
  2: "bg-signal-amber/15 text-signal-amber border border-signal-amber/30",
  3: "bg-obsidian-800 text-ink-dim border border-line",
}

export function SourcesList({ sources }: Props) {
  if (!sources || sources.length === 0) return null
  const sorted = [...sources].sort((a, b) => (b.relevanceScore ?? 0) - (a.relevanceScore ?? 0))
  return (
    <section aria-label="Sources" className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Sources ({sorted.length})
      </h3>
      <ul className="flex flex-col gap-3">
        {sorted.map((s) => {
          const rel = s.publishDate
            ? formatDistanceToNow(new Date(s.publishDate), { addSuffix: true, locale: fr })
            : ""
          return (
            <li key={s.newsId}>
              <a
                href={s.url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`Lire l'article sur ${s.sourceName}`}
                className="block rounded-lg p-3 hover:bg-muted/60 transition-colors"
              >
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{s.sourceName}</span>
                  {rel && <span>· {rel}</span>}
                  <span className={`ml-auto rounded-full px-2 py-0.5 text-[10px] font-semibold ${tierBadgeClass[s.sourceTier]}`}>
                    T{s.sourceTier}
                  </span>
                </div>
                <div className="mt-1 text-sm font-medium">{s.title}</div>
                {s.excerpt && (
                  <div className="mt-1 text-sm italic text-muted-foreground">« {s.excerpt} »</div>
                )}
              </a>
            </li>
          )
        })}
      </ul>
    </section>
  )
}
