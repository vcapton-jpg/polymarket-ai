import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { ArrowUpRight, TrendingUp, Trophy, Target, Zap } from "lucide-react"
import { MetricCard } from "../components/ui/MetricCard"
import { SignalCard } from "../components/signals/SignalCard"
import { LiveIndicator } from "../components/signals/LiveIndicator"
import { EmptyState } from "../components/ui/EmptyState"
import { SkeletonCard } from "../components/ui/Skeleton"
import { useSignals } from "../hooks/useSignals"
import { useDashboardKpis } from "../hooks/useAnalytics"
import { useWebSocket } from "../hooks/useWebSocket"
import { useAuth } from "../lib/auth"
import { mergeSignalsDedupe } from "../lib/utils"

const stagger = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06 } },
}
const fadeUp = {
  hidden: { opacity: 0, y: 10, filter: "blur(4px)" },
  visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.35 } },
}

function getGreeting(): string {
  const h = new Date().getHours()
  if (h < 12) return "Good morning"
  if (h < 18) return "Good afternoon"
  return "Good evening"
}

export default function Dashboard() {
  const { data: signalsData, isLoading: loadingSignals } = useSignals({
    limit: 8,
    refetchInterval: 12_000,
    refetchOnWindowFocus: true,
  })
  const { data: kpis } = useDashboardKpis({ refetchInterval: 30_000 })
  const { connected, liveSignals } = useWebSocket()
  const { user } = useAuth()

  const allSignals = mergeSignalsDedupe(
    liveSignals,
    signalsData?.signals ?? [],
    8,
  )

  const firstName = user?.email?.split("@")[0] ?? "trader"

  return (
    <div className="max-w-[1080px] mx-auto">
      {/* ─── Header ─── */}
      <div className="flex items-center justify-between gap-4 mb-8 flex-wrap">
        <div>
          <motion.h1
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="text-xl md:text-2xl font-display font-bold tracking-display text-txt-primary mb-1"
          >
            {getGreeting()}, {firstName}
          </motion.h1>
          <p className="text-sm text-txt-muted">
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>
        <LiveIndicator connected={connected} />
      </div>

      {/* ─── KPIs ─── */}
      <motion.div
        className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-10"
        variants={stagger}
        initial="hidden"
        animate="visible"
      >
        {[
          {
            label: "Signals Today",
            value: kpis ? String(kpis.signals_today) : "--",
            sub: kpis ? `${kpis.total_signals} total` : "Loading...",
            icon: <Zap size={16} />,
            mono: true,
          },
          {
            label: "Win Rate",
            value: kpis?.win_rate != null ? `${kpis.win_rate.toFixed(1)}%` : "--",
            sub: kpis?.resolved_signals
              ? `${kpis.wins}W / ${kpis.losses}L (${kpis.resolved_signals} resolved)`
              : "Pending first resolved signal",
            icon: <Trophy size={16} />,
            mono: true,
          },
          {
            label: "Avg Score",
            value: kpis?.avg_score != null ? kpis.avg_score.toFixed(1) : "--",
            sub: "Across all signals",
            icon: <Target size={16} />,
            mono: true,
          },
          {
            label: kpis?.streak_type === "win" ? "Win Streak" : kpis?.streak_type === "loss" ? "Loss Streak" : "Streak",
            value: kpis?.streak ? `${kpis.streak}${kpis.streak_type === "win" ? "W" : "L"}` : "--",
            sub: kpis?.best_signal ? `Best: #${kpis.best_signal.signal_id} (${kpis.best_signal.score})` : "Tracking since launch",
            icon: <TrendingUp size={16} />,
            mono: true,
          },
        ].map((kpiItem) => (
          <motion.div key={kpiItem.label} variants={fadeUp}>
            <MetricCard {...kpiItem} />
          </motion.div>
        ))}
      </motion.div>

      {/* ─── Signal Feed ─── */}
      <section>
        <div className="flex items-start justify-between gap-4 mb-5 flex-wrap">
          <div>
            <h2 className="text-base font-display font-semibold text-txt-primary mb-1">
              Live Signal Feed
            </h2>
            <p className="text-xs text-txt-muted max-w-md leading-relaxed">
              Each signal = breaking news + matching Polymarket contract.
              Score = conviction. Market says = current YES probability.
            </p>
          </div>
          <Link to="/opportunities" className="no-underline shrink-0">
            <button
              type="button"
              className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-semibold rounded-lg glass-card border border-edge-subtle text-txt-secondary hover:text-accent hover:border-accent/15 transition-all"
            >
              View all
              <ArrowUpRight size={14} />
            </button>
          </Link>
        </div>

        {loadingSignals ? (
          <div className="flex flex-col gap-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        ) : allSignals.length === 0 ? (
          <EmptyState
            title="No signals in the feed yet"
            message="When breaking news maps to a liquid Polymarket contract, signals appear here automatically."
          />
        ) : (
          <motion.div
            className="flex flex-col gap-3"
            variants={stagger}
            initial="hidden"
            animate="visible"
          >
            {allSignals.map((s, i) => (
              <motion.div key={s.id} variants={fadeUp}>
                <SignalCard
                  signal={s}
                  showLive={i === 0 && liveSignals.length > 0}
                  isNew={liveSignals.some((ls) => ls.id === s.id) && i < 3}
                />
              </motion.div>
            ))}
          </motion.div>
        )}
      </section>
    </div>
  )
}
