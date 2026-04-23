import { useState } from "react"
import { formatDistanceToNow } from "date-fns"
import { fr } from "date-fns/locale"
import type { TimelineEvent } from "@/types/signal"

type Props = { events: TimelineEvent[] }

const PAGE_SIZE = 8

const typeIcon: Record<TimelineEvent["type"], string> = {
  news: "📰",
  market_move: "📈",
}

export function SignalTimeline({ events }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (!events || events.length === 0) return null

  const sorted = [...events].sort(
    (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime(),
  )

  const visible = expanded ? sorted : sorted.slice(0, PAGE_SIZE)
  const remaining = sorted.length - PAGE_SIZE

  return (
    <section aria-label="Chronologie" className="rounded-xl border border-border bg-card p-4">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground mb-3">
        Chronologie
      </h3>
      <ol className="relative border-l border-border ml-2 flex flex-col gap-4">
        {visible.map((event, i) => {
          const rel = formatDistanceToNow(new Date(event.at), { addSuffix: true, locale: fr })
          return (
            <li key={i} className="ml-4">
              <span className="absolute -left-1.5 flex h-3 w-3 items-center justify-center rounded-full bg-muted ring-2 ring-background" />
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <span aria-hidden>{typeIcon[event.type]}</span>
                <span className="font-medium text-foreground">{event.source}</span>
                <span>· {rel}</span>
              </div>
              {event.headline && (
                <p className="mt-0.5 text-sm font-medium">{event.headline}</p>
              )}
              {event.detail && (
                <p className="mt-0.5 text-xs text-muted-foreground">{event.detail}</p>
              )}
            </li>
          )
        })}
      </ol>
      {!expanded && remaining > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-3 text-xs text-muted-foreground hover:text-foreground underline"
        >
          Voir plus ({remaining})
        </button>
      )}
    </section>
  )
}
