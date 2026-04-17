import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence, type MotionStyle } from "framer-motion"
import {
  Search, Brain, Target, Zap, Shield, FileText, Activity,
  ArrowRight, Radio,
} from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { Skeleton } from "../components/ui/Skeleton"
import { api, queryKeys } from "../lib/api"
import { cn, timeAgo } from "../lib/utils"
import type { AgentInfo } from "../lib/types"

const AGENT_META: Record<string, { icon: React.ReactNode; color: string; what: string; example: string }> = {
  scout: {
    icon: <Search size={20} />,
    color: "#3b82f6",
    what: "Monitors 50+ news sources in real time — wire agencies, financial media, X/Twitter — and detects breaking stories that could move prediction markets.",
    example: "Detected AP breaking story on Iran sanctions 12s after publication",
  },
  analyst: {
    icon: <Brain size={20} />,
    color: "#a855f7",
    what: "Runs deep semantic analysis on each event: embeds the story, matches it against 600+ Polymarket contracts, and scores the link's strength.",
    example: "Matched Iran oil story to 3 contracts with ≥0.82 cosine similarity",
  },
  strategist: {
    icon: <Target size={20} />,
    color: "#f59e0b",
    what: "Evaluates market microstructure — liquidity, spread, price positioning — and decides if the opportunity is actually tradeable, not just interesting.",
    example: "Flagged $90/bbl contract: tight spread (2%), high volume, 34% YES",
  },
  trader: {
    icon: <Zap size={20} />,
    color: "#10b981",
    what: "Executes trades on Polymarket when a signal passes all quality gates. Sizes positions based on conviction score and portfolio allocation rules.",
    example: "Placed BUY YES $250 on oil contract at 34¢ — 2.9x potential",
  },
  risk_manager: {
    icon: <Shield size={20} />,
    color: "#ef4444",
    what: "Continuously monitors open positions, checks for adverse price moves, and enforces stop-loss and exposure limits across your portfolio.",
    example: "Triggered alert: NATO summit position dropped 15% — review suggested",
  },
  reporter: {
    icon: <FileText size={20} />,
    color: "#06b6d4",
    what: "Compiles daily intelligence briefs summarizing new signals, resolved markets, win/loss stats, and portfolio performance trends.",
    example: "Generated daily brief: 12 signals, 3 resolved (2W/1L), +$180 P&L",
  },
}

function AgentCard({ agent, selected, onSelect }: {
  agent: AgentInfo; selected: boolean; onSelect: () => void
}) {
  const meta = AGENT_META[agent.id]
  const color = meta?.color || "#888"
  return (
    <motion.div
      whileHover={{ scale: 1.01 }}
      whileTap={{ scale: 0.99 }}
      onClick={onSelect}
      className={cn(
        "cursor-pointer rounded-xl p-5 transition-all duration-300",
        "glass-card glass-card-hover border border-edge-subtle shadow-card",
        selected && "shadow-glow shadow-card-hover ring-1 ring-accent/25",
      )}
      style={{
        ...(selected ? { borderColor: `${color}55`, boxShadow: `0 0 28px ${color}18, 0 8px 24px rgba(0,0,0,0.45)` } : {}),
      } as MotionStyle}
    >
      <div className="flex items-center gap-3 mb-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center shadow-inner-glow border border-edge-subtle"
          style={{ background: `${color}18`, color }}
        >
          {meta?.icon || <Activity size={20} />}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-bold font-display tracking-display text-txt-primary">{agent.name}</h4>
          <p className="text-[11px] text-txt-muted truncate">{agent.role}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: agent.status === "active" ? "#10b981" : "#6b7280",
              boxShadow: agent.status === "active" ? "0 0 8px rgba(16,185,129,0.45)" : "none",
            }}
          />
          <span className="text-[10px] text-txt-muted uppercase tracking-wider">{agent.status}</span>
        </div>
      </div>

      <p className="text-xs text-txt-secondary leading-relaxed mb-3">
        {meta?.what || "Specialized AI agent processing data for your signals."}
      </p>

      {meta?.example && (
        <div className="rounded-lg border border-edge-subtle bg-surface-0/60 backdrop-blur-sm px-3 py-2 mb-3 shadow-inner-glow">
          <p className="text-[10px] text-txt-muted uppercase tracking-wider mb-0.5 font-display">Latest action</p>
          <p className="text-[11px] text-txt-secondary italic">{meta.example}</p>
        </div>
      )}

      <div className="flex items-center justify-between pt-2 border-t border-edge-subtle">
        <span className="text-xs text-txt-muted font-mono">{agent.total_actions} actions</span>
        {agent.last_activity && (
          <span className="text-[10px] text-txt-muted">
            {timeAgo(agent.last_activity.at)} ago
          </span>
        )}
      </div>
    </motion.div>
  )
}

const PIPELINE_STEPS = [
  { agent: "scout", label: "Detect" },
  { agent: "analyst", label: "Analyze" },
  { agent: "strategist", label: "Evaluate" },
  { agent: "trader", label: "Execute" },
  { agent: "risk_manager", label: "Monitor" },
  { agent: "reporter", label: "Report" },
]

export default function Agents() {
  const [selectedAgent, setSelectedAgent] = useState<string | undefined>(undefined)

  const { data: statusData, isLoading: loadingStatus } = useQuery({
    queryKey: queryKeys.agentsStatus,
    queryFn: () => api.agentsStatus(),
    refetchInterval: 10000,
  })

  const { data: activityData, isLoading: loadingActivity } = useQuery({
    queryKey: queryKeys.agentActivity(selectedAgent),
    queryFn: () => api.agentActivity(selectedAgent),
    refetchInterval: 5000,
  })

  return (
    <div>
      <PageHeader
        title="AI Agents"
        subtitle="Your autonomous intelligence pipeline — from breaking news to actionable signals"
      />

      {/* Pipeline visualization */}
      <Card className="mb-6 p-5 shadow-card shadow-glass">
        <h3 className="font-display tracking-display text-xs font-bold text-txt-muted uppercase mb-4">
          How the pipeline works
        </h3>
        <div className="flex items-center gap-1 overflow-x-auto pb-1">
          {PIPELINE_STEPS.map((step, i) => {
            const meta = AGENT_META[step.agent]
            const isStepSelected = selectedAgent === step.agent
            return (
              <div key={step.agent} className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => setSelectedAgent(selectedAgent === step.agent ? undefined : step.agent)}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-lg transition-all cursor-pointer border",
                    isStepSelected
                      ? "glass-card border-edge-subtle shadow-glow shadow-card"
                      : "border-transparent bg-surface-0/40 hover:bg-surface-raised/60 hover:border-edge-subtle hover:shadow-glass",
                  )}
                >
                  <div
                    className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 border border-edge-subtle shadow-inner-glow"
                    style={{ background: `${meta?.color}18`, color: meta?.color }}
                  >
                    {meta?.icon}
                  </div>
                  <span className="text-xs font-semibold font-display tracking-display text-txt-secondary">
                    {step.label}
                  </span>
                </button>
                {i < PIPELINE_STEPS.length - 1 && (
                  <ArrowRight size={14} className="text-edge shrink-0 mx-0.5 opacity-70" />
                )}
              </div>
            )
          })}
        </div>
        <p className="text-[11px] text-txt-muted mt-3 leading-relaxed border-t border-edge-subtle pt-3">
          Each agent handles one stage of the pipeline. A breaking news story flows through all 6 agents in sequence: detection, analysis, market evaluation, execution, risk monitoring, and daily reporting. Click an agent to filter its activity.
        </p>
      </Card>

      {/* Agent grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
        {loadingStatus ? (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height={200} />)
        ) : (
          statusData?.agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              selected={selectedAgent === agent.id}
              onSelect={() =>
                setSelectedAgent(selectedAgent === agent.id ? undefined : agent.id)
              }
            />
          ))
        )}
      </div>

      {/* Activity feed */}
      <Card className="overflow-hidden p-0 shadow-card shadow-glass">
        <div className="p-4 flex items-center justify-between border-b border-edge-subtle bg-surface-0/30">
          <h3 className="text-sm font-semibold font-display tracking-display text-txt-primary flex items-center gap-2">
            <Radio size={16} className="text-success drop-shadow-[0_0_8px_rgba(16,185,129,0.35)]" />
            {selectedAgent
              ? `${statusData?.agents.find(a => a.id === selectedAgent)?.name} Activity`
              : "Live Agent Activity"
            }
          </h3>
          {selectedAgent && (
            <button
              onClick={() => setSelectedAgent(undefined)}
              className="text-xs text-accent-bright hover:text-accent font-display tracking-display bg-transparent border-none cursor-pointer transition-colors"
            >
              Show all
            </button>
          )}
        </div>

        {loadingActivity ? (
          <div className="p-4 flex flex-col gap-3">
            <Skeleton height={50} />
            <Skeleton height={50} />
            <Skeleton height={50} />
          </div>
        ) : !activityData?.activities?.length ? (
          <div className="p-8 text-center">
            <Activity size={32} className="text-txt-muted/30 mx-auto mb-3" />
            <p className="text-sm text-txt-muted mb-1 font-display">No activity yet</p>
            <p className="text-xs text-txt-muted/60 max-w-md mx-auto">Agent activities will appear here as they process news, match markets, and generate signals in real time.</p>
          </div>
        ) : (
          <div className="max-h-[500px] overflow-y-auto divide-y divide-edge-subtle">
            <AnimatePresence initial={false}>
              {activityData.activities.map((act) => {
                const meta = AGENT_META[act.agent]
                const color = meta?.color || "#888"
                return (
                  <motion.div
                    key={act.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="px-4 py-3 flex items-start gap-3 hover:bg-surface-raised/25 transition-colors"
                  >
                    <div
                      className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 border border-edge-subtle shadow-inner-glow"
                      style={{ background: `${color}18`, color }}
                    >
                      {meta?.icon || <Activity size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-semibold font-display tracking-display" style={{ color }}>
                          {act.agent_name}
                        </span>
                        <span className="text-[10px] text-txt-muted bg-surface-raised border border-edge-subtle px-1.5 py-0.5 rounded-md">
                          {act.action}
                        </span>
                      </div>
                      <p className="text-sm text-txt-secondary leading-snug">{act.summary}</p>
                      <span className="text-[10px] text-txt-muted mt-1 block">
                        {timeAgo(act.at)} ago
                      </span>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
          </div>
        )}
      </Card>
    </div>
  )
}
