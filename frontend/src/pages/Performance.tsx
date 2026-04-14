import { useMemo } from "react"
import { motion } from "framer-motion"
import { TrendingUp, Target, Award, Clock, Zap, BarChart3, Trophy, ArrowUpRight, ArrowDownRight } from "lucide-react"
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  LineChart,
  Line,
  Cell,
  PieChart,
  Pie,
} from "recharts"
import { MetricCard } from "../components/ui/MetricCard"
import { Card } from "../components/ui/Card"
import { EmptyState } from "../components/ui/EmptyState"
import { Skeleton } from "../components/ui/Skeleton"
import { useAccuracy, useSimulatedPnl } from "../hooks/useAnalytics"
import { useSignals } from "../hooks/useSignals"
import { BUCKETS } from "../lib/constants"

const SCORE_RANGES = [
  { range: "50-59", min: 50, max: 59, color: "#6B7280" },
  { range: "60-69", min: 60, max: 69, color: "#F59E0B" },
  { range: "70-79", min: 70, max: 79, color: "#F97316" },
  { range: "80-89", min: 80, max: 89, color: "#F97316" },
  { range: "90-100", min: 90, max: 100, color: "#10B981" },
]

const tooltipStyle = {
  background: "#1A2236",
  border: "1px solid rgba(255,255,255,0.10)",
  borderRadius: 8,
  fontSize: 12,
  color: "#F1F5F9",
}

const fadeUp = {
  hidden: { opacity: 0, y: 8 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
}

export default function Performance() {
  const { data: accuracy, isLoading } = useAccuracy()
  const { data: signalsData } = useSignals({ limit: 200 })
  const { data: pnl } = useSimulatedPnl()

  const scoreDistribution = useMemo(() => {
    if (!signalsData?.signals) return SCORE_RANGES.map((r) => ({ ...r, count: 0 }))
    return SCORE_RANGES.map((r) => ({
      ...r,
      count: signalsData.signals.filter((s) => s.signal_score >= r.min && s.signal_score <= r.max).length,
    }))
  }, [signalsData])

  const bucketStats = useMemo(() => {
    if (!accuracy?.by_bucket) return []
    return Object.entries(accuracy.by_bucket)
      .map(([name, stats]) => {
        const s = stats as Record<string, number>
        const bucket = BUCKETS.find((b) => b.value === name)
        return {
          name: bucket?.label ?? name,
          value: name,
          total: s.total ?? 0,
          resolved: s.resolved ?? 0,
          correct: s.correct ?? 0,
          winRate: s.resolved > 0 ? Math.round((s.correct / s.resolved) * 100) : null,
          color: bucket?.color ?? "#94A3B8",
        }
      })
      .sort((a, b) => b.total - a.total)
  }, [accuracy])

  const bestCategory = useMemo(() => {
    const resolved = bucketStats.filter((b) => b.winRate !== null && b.resolved >= 2)
    if (!resolved.length) return null
    return resolved.sort((a, b) => (b.winRate ?? 0) - (a.winRate ?? 0))[0]
  }, [bucketStats])

  const avgWinScore = useMemo(() => {
    if (!signalsData?.signals || !accuracy?.resolved_signals) return null
    const highScoreSignals = signalsData.signals.filter((s) => s.signal_score >= 75)
    if (!highScoreSignals.length) return null
    return Math.round(highScoreSignals.reduce((a, b) => a + b.signal_score, 0) / highScoreSignals.length)
  }, [signalsData, accuracy])

  const timelineData = useMemo(() => {
    if (!signalsData?.signals) return []
    const byDay = new Map<string, number>()
    signalsData.signals.forEach((s) => {
      const day = s.created_at.split("T")[0]
      byDay.set(day, (byDay.get(day) ?? 0) + 1)
    })
    let cumulative = 0
    return [...byDay.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([day, count]) => {
        cumulative += count
        return { day: day.slice(5), signals: count, cumulative }
      })
  }, [signalsData])

  const bucketDonutData = useMemo(() => {
    return bucketStats.filter((b) => b.total > 0).map((b) => ({
      name: b.name,
      value: b.total,
      fill: b.color,
    }))
  }, [bucketStats])

  if (isLoading) {
    return (
      <div className="max-w-[1080px]">
        <div className="flex items-center gap-3 mb-6">
          <TrendingUp size={20} className="text-accent" />
          <h1 className="text-xl md:text-2xl font-bold text-txt-primary">Performance</h1>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height={80} />)}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton height={280} />
          <Skeleton height={280} />
        </div>
      </div>
    )
  }

  const hasData = (accuracy?.total_signals ?? 0) > 0

  return (
    <div className="max-w-[1080px]">
      <div className="flex items-center gap-3 mb-1">
        <TrendingUp size={20} className="text-accent" />
        <h1 className="text-xl md:text-2xl font-bold text-txt-primary tracking-tight">Performance</h1>
      </div>
      <p className="text-sm text-txt-muted mb-6">
        {hasData ? "Track record across all signals generated" : "Performance metrics will populate as signals are generated and resolved"}
      </p>

      <motion.div initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
        {/* KPIs */}
        <motion.div variants={fadeUp} className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
          <MetricCard label="Total Signals" value={accuracy?.total_signals ?? 0} icon={<Zap size={16} />} />
          <MetricCard label="Resolved" value={accuracy?.resolved_signals ?? 0} icon={<Target size={16} />} />
          <MetricCard
            label="Win Rate"
            value={accuracy?.accuracy_pct != null ? `${accuracy.accuracy_pct.toFixed(1)}%` : "--"}
            sub={accuracy?.resolved_signals === 0 ? "Requires resolved markets" : `${accuracy?.correct_signals ?? 0} correct`}
            icon={<Award size={16} />}
            mono
          />
          <MetricCard
            label="Avg Win Score"
            value={avgWinScore != null ? String(avgWinScore) : "--"}
            sub={avgWinScore != null ? "High conviction signals" : "Pending data"}
            icon={<BarChart3 size={16} />}
            mono
          />
          <MetricCard
            label="Best Category"
            value={bestCategory ? bestCategory.name : "--"}
            sub={bestCategory?.winRate != null ? `${bestCategory.winRate}% win rate` : "Pending win data"}
            icon={<Trophy size={16} />}
          />
          <MetricCard
            label="Simulated P&L"
            value={pnl?.simulated_pnl_pct != null
              ? `${pnl.simulated_pnl_pct > 0 ? "+" : ""}${pnl.simulated_pnl_pct.toFixed(1)}%`
              : "--"}
            sub={pnl?.resolved_signals ? `${pnl.resolved_signals} resolved trades` : "Pending resolved data"}
            icon={pnl?.simulated_pnl_pct != null && pnl.simulated_pnl_pct > 0
              ? <ArrowUpRight size={16} className="text-success" />
              : <ArrowDownRight size={16} />}
            mono
          />
        </motion.div>

        {!hasData ? (
          <motion.div variants={fadeUp}>
            <EmptyState
              title="No signals yet"
              message="Performance metrics, charts, and win rate analysis will appear here once the pipeline starts generating signals. Markets typically resolve in 2-8 weeks."
            />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
              <Card className="p-5 text-center">
                <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-3">
                  <Zap size={18} className="text-accent" />
                </div>
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Signal Generation</h3>
                <p className="text-xs text-txt-muted">Breaking news is matched to Polymarket contracts and scored in real-time.</p>
              </Card>
              <Card className="p-5 text-center">
                <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-3">
                  <Clock size={18} className="text-accent" />
                </div>
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Market Resolution</h3>
                <p className="text-xs text-txt-muted">Prediction markets resolve when outcomes are known -- typically 2-8 weeks.</p>
              </Card>
              <Card className="p-5 text-center">
                <div className="w-10 h-10 rounded-full bg-accent/10 flex items-center justify-center mx-auto mb-3">
                  <Target size={18} className="text-accent" />
                </div>
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Win Rate Tracking</h3>
                <p className="text-xs text-txt-muted">Every signal is tracked against outcomes to measure real accuracy.</p>
              </Card>
            </div>
          </motion.div>
        ) : (
          <>
            {/* Charts row 1 */}
            <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Score Distribution</h3>
                <p className="text-[11px] text-txt-muted mb-4">Higher scores = higher conviction</p>
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={scoreDistribution} barSize={32}>
                    <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                    <XAxis dataKey="range" tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {scoreDistribution.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Card>

              <Card className="p-5">
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Category Breakdown</h3>
                <p className="text-[11px] text-txt-muted mb-4">Signal distribution + win rate by category</p>
                {bucketDonutData.length === 0 ? (
                  <div className="flex items-center justify-center py-12 text-xs text-txt-muted">No category data yet</div>
                ) : (
                  <div className="flex items-center gap-4">
                    <ResponsiveContainer width={140} height={140}>
                      <PieChart>
                        <Pie
                          data={bucketDonutData}
                          cx="50%"
                          cy="50%"
                          innerRadius={40}
                          outerRadius={65}
                          paddingAngle={2}
                          dataKey="value"
                          strokeWidth={0}
                        >
                          {bucketDonutData.map((entry, i) => (
                            <Cell key={i} fill={entry.fill} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                    <div className="flex-1 flex flex-col gap-2">
                      {bucketStats.slice(0, 6).map((b) => (
                        <div key={b.value} className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: b.color }} />
                          <span className="text-xs text-txt-secondary flex-1 truncate">{b.name}</span>
                          <span className="text-xs font-mono text-txt-muted font-tabular">
                            {b.total} {b.winRate != null ? `(${b.winRate}%)` : ""}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            </motion.div>

            {/* Charts row 2 */}
            <motion.div variants={fadeUp} className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Signal Timeline</h3>
                <p className="text-[11px] text-txt-muted mb-4">Cumulative signals over time</p>
                {timelineData.length < 2 ? (
                  <div className="flex flex-col items-center justify-center py-10 gap-2 text-center">
                    <Clock size={20} className="text-txt-muted" />
                    <p className="text-xs text-txt-muted">Collecting data -- chart appears after multiple days of signals.</p>
                  </div>
                ) : (
                  <ResponsiveContainer width="100%" height={220}>
                    <LineChart data={timelineData}>
                      <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
                      <XAxis dataKey="day" tick={{ fill: "#6B7280", fontSize: 10 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#6B7280", fontSize: 11 }} axisLine={false} tickLine={false} width={28} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Line
                        type="monotone"
                        dataKey="cumulative"
                        stroke="#F59E0B"
                        strokeWidth={2}
                        dot={{ fill: "#F59E0B", r: 2 }}
                        activeDot={{ r: 4, stroke: "#F59E0B", strokeWidth: 2 }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </Card>

              <Card className="p-5">
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Win Rate by Score Tier</h3>
                <p className="text-[11px] text-txt-muted mb-4">Do higher scores produce better results?</p>
                {pnl?.by_score_tier && Object.keys(pnl.by_score_tier).length > 0 ? (
                  <div className="flex flex-col gap-4">
                    {Object.entries(pnl.by_score_tier)
                      .sort(([a], [b]) => b.localeCompare(a))
                      .map(([tier, data]) => {
                        const total = data.wins + data.losses
                        const wr = total > 0 ? Math.round((data.wins / total) * 100) : 0
                        const color = wr >= 60 ? "#10B981" : wr >= 50 ? "#F59E0B" : "#EF4444"
                        return (
                          <div key={tier}>
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs font-semibold text-txt-primary">{tier}</span>
                              <span className="text-xs font-mono font-tabular" style={{ color }}>
                                {wr}% ({data.wins}W / {data.losses}L)
                              </span>
                            </div>
                            <div className="h-2.5 rounded-full overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                              <div
                                className="h-full rounded-full transition-all duration-700"
                                style={{ width: `${wr}%`, background: color }}
                              />
                            </div>
                          </div>
                        )
                      })}
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-10 gap-2 text-center">
                    <Target size={20} className="text-txt-muted" />
                    <p className="text-xs text-txt-muted max-w-xs">
                      Score vs outcome analysis will appear after first market resolutions.
                    </p>
                  </div>
                )}
              </Card>
            </motion.div>

            {/* Category win rates */}
            <motion.div variants={fadeUp}>
              <Card className="p-5">
                <h3 className="text-sm font-semibold text-txt-primary mb-1">Category Win Rates</h3>
                <p className="text-[11px] text-txt-muted mb-4">Performance breakdown by topic</p>
                <div className="flex flex-col gap-3">
                  {bucketStats.length === 0 ? (
                    <p className="text-xs text-txt-muted py-8 text-center">No category data yet</p>
                  ) : (
                    bucketStats.map((b) => (
                      <div key={b.name} className="flex items-center gap-3">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ background: b.color }} />
                        <span className="text-xs font-medium text-txt-secondary w-24 truncate">{b.name}</span>
                        <div className="flex-1 h-5 rounded overflow-hidden" style={{ background: "rgba(255,255,255,0.06)" }}>
                          <div
                            className="h-full rounded transition-all duration-500"
                            style={{
                              width: `${Math.max(4, (b.total / Math.max(...bucketStats.map((x) => x.total), 1)) * 100)}%`,
                              background: b.color,
                              opacity: 0.7,
                            }}
                          />
                        </div>
                        <span className="text-xs font-mono text-txt-muted w-20 text-right font-tabular">
                          {b.winRate !== null ? `${b.winRate}%` : "--"} ({b.resolved}/{b.total})
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </Card>
            </motion.div>
          </>
        )}
      </motion.div>
    </div>
  )
}
