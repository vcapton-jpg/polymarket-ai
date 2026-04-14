import { motion } from "framer-motion"
import { BarChart3, CheckCircle, XCircle, TrendingUp, Trophy } from "lucide-react"
import { Card } from "../components/ui/Card"
import { Badge } from "../components/ui/Badge"
import { Skeleton } from "../components/ui/Skeleton"
import { useTrackRecord, useSimulatedPnl } from "../hooks/useAnalytics"
import { BUCKETS } from "../lib/constants"
import { cn } from "../lib/utils"

const fadeUp = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.35 } },
}
const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}

export default function TrackRecord() {
  const { data: track, isLoading } = useTrackRecord()
  const { data: pnl } = useSimulatedPnl(60)

  if (isLoading) {
    return (
      <div className="max-w-[900px] mx-auto">
        <Skeleton height={32} width="50%" />
        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => <Skeleton key={i} height={100} />)}
        </div>
        <Skeleton height={200} className="mt-6" />
      </div>
    )
  }

  const wr = track?.overall_win_rate
  const bucketEntries = Object.entries(track?.by_bucket ?? {})
  const bucketLookup = Object.fromEntries(BUCKETS.map((b) => [b.value, b]))

  return (
    <div className="max-w-[900px] mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <Trophy size={20} className="text-accent" />
        <h1 className="text-xl md:text-2xl font-bold text-txt-primary tracking-tight">
          Track Record
        </h1>
      </div>
      <p className="text-sm text-txt-muted mb-8">
        Public, verifiable performance history. Every signal is tracked from creation to market resolution.
      </p>

      {/* Top KPIs */}
      <motion.div
        className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8"
        variants={stagger}
        initial="hidden"
        animate="visible"
      >
        <motion.div variants={fadeUp}>
          <Card className="p-4 text-center">
            <p className="text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-1">Total Signals</p>
            <p className="font-mono text-2xl font-bold text-txt-primary">{track?.total_signals ?? 0}</p>
          </Card>
        </motion.div>
        <motion.div variants={fadeUp}>
          <Card className="p-4 text-center">
            <p className="text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-1">Resolved</p>
            <p className="font-mono text-2xl font-bold text-txt-primary">{track?.resolved_signals ?? 0}</p>
          </Card>
        </motion.div>
        <motion.div variants={fadeUp}>
          <Card className="p-4 text-center">
            <p className="text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-1">Win Rate</p>
            <p className={cn(
              "font-mono text-2xl font-bold",
              wr != null && wr >= 60 ? "text-success" : wr != null && wr < 50 ? "text-danger" : "text-txt-primary",
            )}>
              {wr != null ? `${wr}%` : "--"}
            </p>
          </Card>
        </motion.div>
        <motion.div variants={fadeUp}>
          <Card className="p-4 text-center">
            <p className="text-[11px] font-semibold text-txt-muted uppercase tracking-wider mb-1">Simulated P&L</p>
            <p className={cn(
              "font-mono text-2xl font-bold",
              pnl?.simulated_pnl_pct != null && pnl.simulated_pnl_pct > 0 ? "text-success" :
              pnl?.simulated_pnl_pct != null && pnl.simulated_pnl_pct < 0 ? "text-danger" : "text-txt-primary",
            )}>
              {pnl?.simulated_pnl_pct != null ? `${pnl.simulated_pnl_pct > 0 ? "+" : ""}${pnl.simulated_pnl_pct.toFixed(1)}%` : "--"}
            </p>
          </Card>
        </motion.div>
      </motion.div>

      {/* Weekly Performance */}
      {track?.weekly && track.weekly.length > 0 && (
        <Card className="p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <BarChart3 size={16} className="text-accent" />
            <h2 className="text-sm font-semibold text-txt-primary">Weekly Performance</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-txt-muted text-[10px] uppercase tracking-wider">
                  <th className="text-left pb-2 pr-4">Week</th>
                  <th className="text-right pb-2 px-3">Signals</th>
                  <th className="text-right pb-2 px-3">Resolved</th>
                  <th className="text-right pb-2 px-3">Correct</th>
                  <th className="text-right pb-2 pl-3">Win Rate</th>
                </tr>
              </thead>
              <tbody>
                {track.weekly.map((w) => (
                  <tr key={w.week} className="border-t" style={{ borderColor: "rgba(255,255,255,0.05)" }}>
                    <td className="py-2 pr-4 font-mono text-txt-secondary">{w.week ?? "--"}</td>
                    <td className="py-2 px-3 text-right font-mono text-txt-primary">{w.total_signals}</td>
                    <td className="py-2 px-3 text-right font-mono text-txt-secondary">{w.resolved}</td>
                    <td className="py-2 px-3 text-right font-mono text-txt-primary">{w.correct}</td>
                    <td className={cn(
                      "py-2 pl-3 text-right font-mono font-semibold",
                      w.win_rate != null && w.win_rate >= 60 ? "text-success" :
                      w.win_rate != null && w.win_rate < 50 ? "text-danger" : "text-txt-muted",
                    )}>
                      {w.win_rate != null ? `${w.win_rate}%` : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* By Category */}
      {bucketEntries.length > 0 && (
        <Card className="p-5 mb-6">
          <h2 className="text-sm font-semibold text-txt-primary mb-4">Win Rate by Category</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {bucketEntries.map(([bkt, data]) => {
              const meta = bucketLookup[bkt]
              return (
                <div key={bkt} className="bg-surface-raised rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    {meta?.emoji && <span className="text-sm">{meta.emoji}</span>}
                    <span className="text-xs font-semibold text-txt-primary">{meta?.label ?? bkt}</span>
                  </div>
                  <p className={cn(
                    "font-mono text-lg font-bold mb-0.5",
                    data.win_rate != null && data.win_rate >= 60 ? "text-success" :
                    data.win_rate != null && data.win_rate < 50 ? "text-danger" : "text-txt-primary",
                  )}>
                    {data.win_rate != null ? `${data.win_rate}%` : "--"}
                  </p>
                  <p className="text-[10px] text-txt-muted">{data.resolved}/{data.total} resolved</p>
                </div>
              )
            })}
          </div>
        </Card>
      )}

      {/* Recent Resolved Signals */}
      {track?.recent_resolved && track.recent_resolved.length > 0 && (
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-txt-primary mb-4">Recent Resolved Signals</h2>
          <div className="flex flex-col gap-2">
            {track.recent_resolved.map((s) => (
              <div
                key={s.signal_id}
                className="flex items-center gap-3 py-2 px-3 rounded-md bg-surface-raised/50"
              >
                {s.direction_correct ? (
                  <CheckCircle size={16} className="text-success shrink-0" />
                ) : (
                  <XCircle size={16} className="text-danger shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-txt-primary truncate">
                    {s.event_title ?? `Signal #${s.signal_id}`}
                  </p>
                  <p className="text-[10px] text-txt-muted">
                    Score {s.score} -- {s.direction}
                  </p>
                </div>
                <Badge
                  color={s.direction_correct ? "#22c55e" : "#ef4444"}
                  label={s.direction_correct ? "CORRECT" : "WRONG"}
                  size="sm"
                />
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Empty state */}
      {!track?.resolved_signals && (
        <Card className="p-8 text-center">
          <TrendingUp size={32} className="text-txt-muted mx-auto mb-3" />
          <p className="text-sm text-txt-secondary font-medium mb-1">No resolved signals yet</p>
          <p className="text-xs text-txt-muted">
            Track record data will appear here once markets with active signals resolve.
          </p>
        </Card>
      )}
    </div>
  )
}
