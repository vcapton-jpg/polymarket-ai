import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence, type MotionStyle } from "framer-motion"
import {
  Search, Brain, Target, Zap, Shield, FileText, Activity,
  ChevronRight,
} from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { Skeleton } from "../components/ui/Skeleton"
import { api, queryKeys } from "../lib/api"
import { cn, timeAgo } from "../lib/utils"
import type { AgentInfo, AgentActivityItem } from "../lib/types"

const AGENT_ICONS: Record<string, React.ReactNode> = {
  scout: <Search size={20} />,
  analyst: <Brain size={20} />,
  strategist: <Target size={20} />,
  trader: <Zap size={20} />,
  risk_manager: <Shield size={20} />,
  reporter: <FileText size={20} />,
}

const AGENT_COLORS: Record<string, string> = {
  scout: "#3b82f6",
  analyst: "#a855f7",
  strategist: "#f59e0b",
  trader: "#10b981",
  risk_manager: "#ef4444",
  reporter: "#06b6d4",
}

function AgentCard({ agent, selected, onSelect }: {
  agent: AgentInfo; selected: boolean; onSelect: () => void
}) {
  const color = AGENT_COLORS[agent.id] || "#888"
  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      onClick={onSelect}
      className={cn(
        "cursor-pointer rounded-lg p-4 transition-all",
        selected ? "bg-surface-raised ring-1" : "bg-surface-card hover:bg-surface-raised",
      )}
      style={(selected ? { ringColor: color, borderColor: `${color}40` } : {}) as MotionStyle}
    >
      <div className="flex items-center gap-3 mb-2">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center"
          style={{ background: `${color}20`, color }}
        >
          {AGENT_ICONS[agent.id] || <Activity size={20} />}
        </div>
        <div className="flex-1 min-w-0">
          <h4 className="text-sm font-semibold text-txt-primary">{agent.name}</h4>
          <p className="text-[11px] text-txt-muted truncate">{agent.role}</p>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className="w-2 h-2 rounded-full"
            style={{
              background: agent.status === "active" ? "#10b981" : "#6b7280",
              boxShadow: agent.status === "active" ? "0 0 6px rgba(16,185,129,0.5)" : "none",
            }}
          />
          <span className="text-[10px] text-txt-muted uppercase">{agent.status}</span>
        </div>
      </div>
      <div className="flex items-center justify-between mt-2 pt-2"
        style={{ borderTop: "1px solid rgba(255,255,255,0.05)" }}
      >
        <span className="text-xs text-txt-muted">{agent.total_actions} actions</span>
        {agent.last_activity && (
          <span className="text-[10px] text-txt-muted">
            {timeAgo(agent.last_activity.at)} ago
          </span>
        )}
      </div>
    </motion.div>
  )
}

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
        title="AI Agent Team"
        subtitle="6 specialized agents working 24/7 for your intelligence"
      />

      {/* Agent grid */}
      <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 mb-6">
        {loadingStatus ? (
          Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} height={110} />)
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
      <Card>
        <div className="p-4 flex items-center justify-between"
          style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
        >
          <h3 className="text-sm font-semibold text-txt-primary flex items-center gap-2">
            <Activity size={16} />
            {selectedAgent
              ? `${statusData?.agents.find(a => a.id === selectedAgent)?.name} Activity`
              : "All Agent Activity"
            }
          </h3>
          {selectedAgent && (
            <button
              onClick={() => setSelectedAgent(undefined)}
              className="text-xs text-accent hover:underline"
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
          <div className="p-8 text-center text-txt-muted text-sm">
            No agent activity yet. Activities will appear as agents process signals and events.
          </div>
        ) : (
          <div className="divide-y divide-white/5 max-h-[500px] overflow-y-auto">
            <AnimatePresence initial={false}>
              {activityData.activities.map((act) => {
                const color = AGENT_COLORS[act.agent] || "#888"
                return (
                  <motion.div
                    key={act.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="px-4 py-3 flex items-start gap-3"
                  >
                    <div
                      className="w-7 h-7 rounded flex items-center justify-center shrink-0 mt-0.5"
                      style={{ background: `${color}15`, color }}
                    >
                      {AGENT_ICONS[act.agent] || <Activity size={14} />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-semibold" style={{ color }}>
                          {act.agent_name}
                        </span>
                        <span className="text-[10px] text-txt-muted bg-surface-raised px-1.5 py-0.5 rounded">
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
