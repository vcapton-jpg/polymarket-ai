import { useState } from "react"
import { motion } from "framer-motion"
import { Radio, ChevronDown, ChevronUp, Info } from "lucide-react"
import { SignalCard } from "../components/signals/SignalCard"
import { SignalFilters } from "../components/signals/SignalFilters"
import { LiveIndicator } from "../components/signals/LiveIndicator"
import { EmptyState } from "../components/ui/EmptyState"
import { SkeletonCard } from "../components/ui/Skeleton"
import { Button } from "../components/ui/Button"
import { useSignals } from "../hooks/useSignals"
import { useWebSocket } from "../hooks/useWebSocket"

const PAGE_SIZE = 20

export default function Opportunities() {
  const [filters, setFilters] = useState({ bucket: "", minScore: "", direction: "" })
  const [offset, setOffset] = useState(0)
  const [showHelp, setShowHelp] = useState(false)
  const { connected, liveSignals } = useWebSocket()

  const { data, isLoading } = useSignals({
    bucket: filters.bucket || undefined,
    min_score: filters.minScore ? Number(filters.minScore) : undefined,
    direction: filters.direction || undefined,
    limit: PAGE_SIZE,
    offset,
  })

  const signals = data?.signals || []
  const total = data?.total || 0
  const hasNext = offset + PAGE_SIZE < total
  const hasPrev = offset > 0

  return (
    <div className="max-w-[900px]">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 mb-2 flex-wrap">
        <div className="flex items-center gap-3">
          <Radio size={20} className="text-accent" />
          <h1 className="text-xl md:text-2xl font-bold text-txt-primary tracking-tight">Signals</h1>
        </div>
        <LiveIndicator connected={connected} />
      </div>
      <p className="text-sm text-txt-muted mb-6">
        <span className="font-mono font-semibold text-accent">{total}</span> opportunities detected from breaking news
      </p>

      {/* How it works - collapsible */}
      <button
        onClick={() => setShowHelp(!showHelp)}
        className="flex items-center gap-2 text-xs text-txt-muted hover:text-txt-secondary mb-4 transition-colors bg-transparent border-none cursor-pointer"
      >
        <Info size={14} />
        <span>How signals work</span>
        {showHelp ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
      </button>

      {showHelp && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="bg-surface-raised rounded-lg p-4 mb-6 text-xs text-txt-secondary leading-relaxed shadow-card"
        >
          <p className="mb-2">
            Each signal = a <span className="text-txt-primary font-medium">breaking news story</span> + a matching <span className="text-txt-primary font-medium">Polymarket contract</span> where the market hasn't yet priced in the news.
          </p>
          <p className="mb-2">
            <span className="text-accent font-semibold">Score</span> = our conviction that the news moves the market. 60+ = actionable, 75+ = high conviction, 90+ = exceptional.
          </p>
          <p>
            <span className="text-accent font-semibold">Market says</span> = current YES implied probability on Polymarket.
          </p>
        </motion.div>
      )}

      {/* Filters */}
      <SignalFilters filters={filters} onChange={(f) => { setFilters(f); setOffset(0) }} />

      {/* Live signals */}
      {liveSignals.length > 0 && offset === 0 && (
        <div className="mb-6">
          <span className="text-[11px] font-bold text-success uppercase tracking-widest mb-2 block">Just In</span>
          <div className="flex flex-col gap-3">
            {liveSignals.slice(0, 3).map((s) => (
              <SignalCard key={`live-${s.id}`} signal={s} showLive isNew />
            ))}
          </div>
        </div>
      )}

      {/* Signal list */}
      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)}
        </div>
      ) : signals.length === 0 ? (
        <EmptyState
          title="No signals match your filters"
          message="Try adjusting the filters or wait for new signals to come in."
        />
      ) : (
        <>
          <div className="flex flex-col gap-3">
            {signals.map((s) => (
              <SignalCard key={s.id} signal={s} />
            ))}
          </div>

          <div className="flex items-center justify-center gap-4 mt-8 pb-8">
            <Button variant="secondary" size="sm" disabled={!hasPrev} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
              Previous
            </Button>
            <span className="text-xs text-txt-muted font-mono font-tabular">
              {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
            </span>
            <Button variant="secondary" size="sm" disabled={!hasNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
              Next
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
