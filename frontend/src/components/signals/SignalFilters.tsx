import { BUCKETS } from "../../lib/constants"
import { cn } from "../../lib/utils"

interface Filters {
  bucket: string
  minScore: string
  direction: string
}

interface Props {
  filters: Filters
  onChange: (f: Filters) => void
}

export function SignalFilters({ filters, onChange }: Props) {
  const update = (key: keyof Filters, val: string) =>
    onChange({ ...filters, [key]: val })

  const allBuckets = [{ value: "", label: "All", emoji: "" }, ...BUCKETS]

  return (
    <div className="flex flex-col gap-3 mb-6">
      {/* Category pills */}
      <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none -mx-1 px-1">
        {allBuckets.map((b) => {
          const active = filters.bucket === b.value
          return (
            <button
              key={b.value}
              onClick={() => update("bucket", b.value)}
              className={cn(
                "flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all duration-200 shrink-0",
                active
                  ? "bg-accent/15 text-accent"
                  : "bg-surface-card text-txt-muted hover:text-txt-secondary",
              )}
              style={{ border: active ? "1px solid rgba(245,158,11,0.35)" : "1px solid rgba(255,255,255,0.08)" }}
            >
              {b.emoji && <span>{b.emoji}</span>}
              <span>{b.label}</span>
            </button>
          )
        })}
      </div>

      {/* Direction + conviction */}
      <div className="flex gap-2 flex-wrap">
        <div className="flex rounded-md overflow-hidden shadow-card">
          {[
            { value: "", label: "All" },
            { value: "BUY_YES", label: "BUY YES" },
            { value: "BUY_NO", label: "BUY NO" },
          ].map((d) => (
            <button
              key={d.value}
              onClick={() => update("direction", d.value)}
              className={cn(
                "px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider transition-colors",
                filters.direction === d.value
                  ? "bg-accent/15 text-accent"
                  : "bg-surface-card text-txt-muted hover:text-txt-secondary hover:bg-surface-raised",
              )}
              style={{ borderRight: "1px solid rgba(255,255,255,0.06)" }}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="flex rounded-md overflow-hidden shadow-card">
          {[
            { value: "", label: "Any" },
            { value: "60", label: "60+" },
            { value: "75", label: "75+" },
            { value: "90", label: "90+" },
          ].map((s) => (
            <button
              key={s.value}
              onClick={() => update("minScore", s.value)}
              className={cn(
                "px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider transition-colors",
                filters.minScore === s.value
                  ? "bg-accent/15 text-accent"
                  : "bg-surface-card text-txt-muted hover:text-txt-secondary hover:bg-surface-raised",
              )}
              style={{ borderRight: "1px solid rgba(255,255,255,0.06)" }}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
