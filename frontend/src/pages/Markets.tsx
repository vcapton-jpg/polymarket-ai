import { useState } from "react"
import { motion } from "framer-motion"
import { BarChart3, ExternalLink } from "lucide-react"
import { DataTable, type Column } from "../components/ui/DataTable"
import { CategoryBadge } from "../components/ui/CategoryBadge"
import { Badge } from "../components/ui/Badge"
import { EmptyState } from "../components/ui/EmptyState"
import { Skeleton } from "../components/ui/Skeleton"
import { useMarkets } from "../hooks/useMarkets"
import { formatUsdCompact, formatYesImpliedPct, formatSpreadPp, cn } from "../lib/utils"
import { BUCKETS } from "../lib/constants"
import type { Market } from "../lib/types"

const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}

export default function Markets() {
  const [category, setCategory] = useState("")
  const [activeOnly, setActiveOnly] = useState(true)

  const { data, isLoading } = useMarkets({
    category: category || undefined,
    active_only: activeOnly,
    limit: 100,
  })

  const markets = data?.markets || []

  const columns: Column<Market>[] = [
    {
      key: "question",
      header: "Question",
      className: "min-w-[200px]",
      render: (m) => (
        <a
          href={`https://polymarket.com/event/${m.market_id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-txt-primary font-medium text-[13px] line-clamp-1 hover:text-accent-bright transition-colors no-underline flex items-center gap-1.5 group"
        >
          {m.question}
          <ExternalLink size={11} className="shrink-0 opacity-0 group-hover:opacity-60 transition-opacity" />
        </a>
      ),
    },
    {
      key: "category",
      header: "Category",
      render: (m) => (
        <CategoryBadge bucket={m.category ?? undefined} question={m.question} />
      ),
    },
    {
      key: "price",
      header: "YES Price",
      className: "text-right",
      sortFn: (a, b) => (a.last_trade_price ?? 0) - (b.last_trade_price ?? 0),
      render: (m) => (
        <span className="text-txt-primary font-mono font-semibold font-tabular text-sm">
          {formatYesImpliedPct(m.last_trade_price)}
        </span>
      ),
    },
    {
      key: "volume",
      header: "Vol 24h",
      className: "text-right",
      sortFn: (a, b) => (a.volume_24h ?? 0) - (b.volume_24h ?? 0),
      render: (m) => (
        <span className="font-mono text-txt-secondary text-sm">
          {formatUsdCompact(m.volume_24h)}
        </span>
      ),
    },
    {
      key: "liquidity",
      header: "Liquidity",
      className: "text-right",
      sortFn: (a, b) => (a.liquidity ?? 0) - (b.liquidity ?? 0),
      render: (m) => (
        <span className="font-mono text-txt-secondary text-sm">
          {m.liquidity ? formatUsdCompact(m.liquidity) : <span className="text-txt-muted">No liquidity</span>}
        </span>
      ),
    },
    {
      key: "spread",
      header: "Spread",
      className: "text-right",
      sortFn: (a, b) => (a.spread ?? 0) - (b.spread ?? 0),
      render: (m) => (
        <span className={cn("font-mono text-sm", m.spread && m.spread > 0.1 ? "text-warning" : "text-txt-secondary")}>
          {formatSpreadPp(m.spread)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (m) =>
        m.closed ? (
          <Badge label="Closed" color="#EF4444" />
        ) : m.active ? (
          <Badge label="Active" color="#10B981" />
        ) : (
          <Badge label="Inactive" color="#6B7280" />
        ),
    },
  ]

  const allBuckets = [{ value: "", label: "All", emoji: "" }, ...BUCKETS]

  return (
    <div className="max-w-[1100px]">
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        {/* Header */}
        <motion.div variants={fadeUp} className="flex items-center gap-3 mb-1">
          <BarChart3 size={20} className="text-accent" />
          <h1 className="font-display text-xl md:text-2xl font-bold text-txt-primary tracking-display">
            Markets
          </h1>
        </motion.div>
        <motion.p variants={fadeUp} className="text-sm text-txt-muted mb-6">
          <span className="inline-block font-mono font-semibold text-gradient-gold">{data?.total ?? 0}</span>{" "}
          Polymarket contracts tracked
        </motion.p>

        {/* Filters */}
        <motion.div variants={fadeUp} className="flex items-center gap-3 mb-6 flex-wrap">
          <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-none">
            {allBuckets.map((b) => {
              const active = category === b.value
              return (
                <button
                  key={b.value}
                  onClick={() => setCategory(b.value)}
                  className={cn(
                    "flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all shrink-0 border",
                    active
                      ? "bg-accent-muted/40 text-accent-bright border-edge-accent shadow-glow"
                      : "bg-surface-card text-txt-muted hover:text-txt-secondary border-edge-subtle hover:border-edge hover:shadow-card",
                  )}
                >
                  {b.emoji && <span>{b.emoji}</span>}
                  {b.label}
                </button>
              )
            })}
          </div>
          <label className="flex items-center gap-2 text-sm text-txt-secondary cursor-pointer">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
              className="accent-accent w-4 h-4 rounded"
            />
            Active only
          </label>
        </motion.div>
      </motion.div>

      {/* Table */}
      {isLoading ? (
        <div className="rounded-xl border border-edge-subtle glass-card shadow-glass p-4 flex flex-col gap-2">
          <Skeleton height={48} />
          <Skeleton height={48} />
          <Skeleton height={48} />
          <Skeleton height={48} />
        </div>
      ) : markets.length === 0 ? (
        <EmptyState title="No markets found" message="Try changing the filters." />
      ) : (
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          className={cn(
            "rounded-xl overflow-hidden border border-edge-subtle glass-card shadow-card",
            "[&_thead_tr]:bg-surface-raised/40",
            "[&_tbody_tr]:transition-all [&_tbody_tr]:duration-200",
            "[&_tbody_tr:hover]:!bg-surface-raised [&_tbody_tr:hover]:shadow-[inset_0_0_0_1px_rgba(212,160,23,0.12)]",
          )}
        >
          <DataTable data={markets} columns={columns} keyFn={(m) => m.market_id} />
        </motion.div>
      )}
    </div>
  )
}
