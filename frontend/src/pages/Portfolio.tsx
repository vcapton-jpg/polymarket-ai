import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Wallet, TrendingUp, TrendingDown, DollarSign, Package, ArrowUpDown } from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { Skeleton } from "../components/ui/Skeleton"
import { EmptyState } from "../components/ui/EmptyState"
import { api, queryKeys } from "../lib/api"
import { cn } from "../lib/utils"

const portfolioContainer = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.06, delayChildren: 0.05 },
  },
}

const fadeUp = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
  },
}

function StatCard({ label, value, sub, trend }: {
  label: string; value: string; sub?: string; trend?: "up" | "down" | "neutral"
}) {
  return (
    <Card className="p-4 shadow-card">
      <span className="text-xs text-txt-muted block mb-1 font-medium">{label}</span>
      <span className={cn(
        "text-2xl font-bold font-mono font-tabular",
        trend === "up" && "text-success",
        trend === "down" && "text-danger",
        (!trend || trend === "neutral") && "text-txt-primary",
      )}>{value}</span>
      {sub && <span className="text-xs text-txt-muted block mt-0.5">{sub}</span>}
    </Card>
  )
}

export default function Portfolio() {
  const { data: portfolio, isLoading } = useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: () => api.portfolio(),
    retry: false,
  })

  const { data: ordersData } = useQuery({
    queryKey: queryKeys.orders(),
    queryFn: () => api.orders(),
    retry: false,
  })

  if (isLoading) {
    return (
      <div className="py-8 flex flex-col gap-4">
        <Skeleton height={32} width="40%" />
        <div className="grid grid-cols-4 gap-4"><Skeleton height={80} /><Skeleton height={80} /><Skeleton height={80} /><Skeleton height={80} /></div>
        <Skeleton height={300} />
      </div>
    )
  }

  if (!portfolio) {
    return (
      <div>
        <PageHeader title="Portfolio" subtitle="Track your positions & P&L" />
        <EmptyState
          icon={<Wallet size={40} className="text-txt-muted" />}
          title="No portfolio yet"
          message="Start trading from the Signals page to create your portfolio."
        />
      </div>
    )
  }

  const totalPnl = portfolio.positions.reduce((sum, p) => sum + (p.pnl_pct || 0), 0)
  const openCount = portfolio.positions.filter(p => p.status === "open").length

  return (
    <div>
      <PageHeader title="Portfolio" subtitle="Your positions & trading activity" />

      <motion.div
        variants={portfolioContainer}
        initial="hidden"
        animate="visible"
      >
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard label="Portfolio Value" value={`$${portfolio.total_value.toLocaleString()}`} />
          <StatCard label="Cash Balance" value={`$${portfolio.cash_balance.toLocaleString()}`} />
          <StatCard label="Open Positions" value={String(openCount)} />
          <StatCard
            label="Total P&L"
            value={`${totalPnl >= 0 ? "+" : ""}${totalPnl.toFixed(1)}%`}
            trend={totalPnl > 0 ? "up" : totalPnl < 0 ? "down" : "neutral"}
          />
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="mb-6 p-0 overflow-hidden shadow-card">
            <div className="p-4 border-b border-edge-subtle bg-surface-0/40">
              <h3 className="text-sm font-semibold font-display tracking-display text-txt-primary flex items-center gap-2">
                <Package size={16} className="text-accent" /> Open Positions
              </h3>
            </div>
            {portfolio.positions.length === 0 ? (
              <div className="p-8 text-center text-txt-muted text-sm">No open positions</div>
            ) : (
              <div className="divide-y divide-edge-subtle">
                {portfolio.positions.map((pos, i) => (
                  <motion.div
                    key={pos.id}
                    className="px-4 py-3 flex items-center justify-between hover:bg-surface-raised/30 transition-colors"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.04, duration: 0.25 }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-txt-primary truncate">
                        {pos.market_question || pos.market_id.slice(0, 30)}
                      </p>
                      <p className="text-xs text-txt-muted mt-0.5">
                        {pos.side} · {pos.size} shares @ {pos.entry_price.toFixed(4)}
                      </p>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <p className={cn(
                        "text-sm font-bold font-mono font-tabular",
                        (pos.pnl_pct || 0) >= 0 ? "text-success" : "text-danger",
                      )}>
                        {(pos.pnl_pct || 0) >= 0 ? "+" : ""}{(pos.pnl_pct || 0).toFixed(1)}%
                      </p>
                      {pos.current_price && (
                        <p className="text-xs text-txt-muted">Now: {pos.current_price.toFixed(4)}</p>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </Card>
        </motion.div>

        <motion.div variants={fadeUp}>
          <Card className="p-0 overflow-hidden shadow-card">
            <div className="p-4 border-b border-edge-subtle bg-surface-0/40">
              <h3 className="text-sm font-semibold font-display tracking-display text-txt-primary flex items-center gap-2">
                <ArrowUpDown size={16} className="text-accent" /> Recent Orders
              </h3>
            </div>
            {!ordersData?.orders?.length ? (
              <div className="p-8 text-center text-txt-muted text-sm">No orders yet</div>
            ) : (
              <div className="divide-y divide-edge-subtle">
                {(ordersData.orders as any[]).slice(0, 10).map((o: any, i: number) => (
                  <motion.div
                    key={o.id}
                    className="px-4 py-3 flex items-center justify-between hover:bg-surface-raised/30 transition-colors"
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.22 }}
                  >
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-txt-primary">{o.side} · {o.market_id.slice(0, 30)}…</p>
                      <p className="text-xs text-txt-muted">{o.order_type} · {o.created_at?.slice(0, 16)}</p>
                    </div>
                    <div className="text-right shrink-0 ml-4">
                      <span className={cn(
                        "text-xs font-semibold px-2 py-0.5 rounded-lg border border-edge-subtle",
                        o.status === "filled" && "bg-success/20 text-success",
                        o.status === "submitted" && "bg-accent-muted text-accent",
                        o.status === "failed" && "bg-danger/20 text-danger",
                        o.status === "pending" && "bg-warning/20 text-warning",
                      )}>
                        {o.status.toUpperCase()}
                      </span>
                      <p className="text-xs text-txt-muted mt-0.5">{o.size} @ {o.price}</p>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </Card>
        </motion.div>
      </motion.div>
    </div>
  )
}
