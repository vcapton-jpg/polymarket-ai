import { useState, useRef, useEffect } from "react"
import { useQuery } from "@tanstack/react-query"
import { motion, AnimatePresence } from "framer-motion"
import {
  Send, Search, Brain, Target, Zap, Shield, FileText, Activity, Bot,
} from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { api, queryKeys } from "../lib/api"
import { cn, timeAgo } from "../lib/utils"

const AGENT_ICONS: Record<string, React.ReactNode> = {
  scout: <Search size={14} />,
  analyst: <Brain size={14} />,
  strategist: <Target size={14} />,
  trader: <Zap size={14} />,
  risk_manager: <Shield size={14} />,
  reporter: <FileText size={14} />,
  system: <Bot size={14} />,
}

const AGENT_COLORS: Record<string, string> = {
  scout: "#3b82f6",
  analyst: "#a855f7",
  strategist: "#f59e0b",
  trader: "#10b981",
  risk_manager: "#ef4444",
  reporter: "#06b6d4",
  system: "#6b7280",
}

interface ChatMessage {
  id: string
  type: "user" | "agent"
  agent?: string
  content: string
  timestamp: Date
}

const QUICK_ACTIONS = [
  { label: "Latest signals", prompt: "/signals" },
  { label: "Portfolio status", prompt: "/portfolio" },
  { label: "Agent status", prompt: "/agents" },
  { label: "Daily brief", prompt: "/brief" },
  { label: "Risk check", prompt: "/risk" },
]

export default function AgentWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      type: "agent",
      agent: "system",
      content: "Welcome to the Agent Workspace. I'm your interface to the Signal AI team. Ask me anything about your signals, portfolio, or agent status. Try a quick action below or type a command.",
      timestamp: new Date(),
    },
  ])
  const [input, setInput] = useState("")
  const [processing, setProcessing] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const { data: activityData } = useQuery({
    queryKey: queryKeys.agentActivity(),
    queryFn: () => api.agentActivity(),
    refetchInterval: 10000,
  })

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages])

  const handleSend = async (text?: string) => {
    const msg = text || input.trim()
    if (!msg || processing) return

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      type: "user",
      content: msg,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setInput("")
    setProcessing(true)

    try {
      let response: ChatMessage

      if (msg.startsWith("/signals")) {
        const data = await api.signals({ limit: 5 })
        const lines = data.signals.map(
          s => `• #${s.id} ${s.direction} — Score ${s.signal_score} — ${timeAgo(s.created_at)} ago`
        )
        response = {
          id: `agent-${Date.now()}`,
          type: "agent",
          agent: "analyst",
          content: lines.length
            ? `**Latest 5 signals:**\n${lines.join("\n")}`
            : "No signals available at the moment.",
          timestamp: new Date(),
        }
      } else if (msg.startsWith("/portfolio")) {
        try {
          const data = await api.portfolio()
          const posLines = data.positions.map(
            p => `• ${p.side} ${(p.market_question || p.market_id).slice(0, 40)} — P&L: ${(p.pnl_pct || 0).toFixed(1)}%`
          )
          response = {
            id: `agent-${Date.now()}`,
            type: "agent",
            agent: "strategist",
            content: `**Portfolio:** $${data.total_value.toLocaleString()} | Cash: $${data.cash_balance.toLocaleString()}\n**${data.positions.length} positions:**\n${posLines.join("\n") || "No open positions"}`,
            timestamp: new Date(),
          }
        } catch {
          response = {
            id: `agent-${Date.now()}`,
            type: "agent",
            agent: "strategist",
            content: "No portfolio found. Start trading from the Signals page!",
            timestamp: new Date(),
          }
        }
      } else if (msg.startsWith("/agents")) {
        const data = await api.agentsStatus()
        const lines = data.agents.map(
          a => `• **${a.name}** — ${a.status} (${a.total_actions} actions)`
        )
        response = {
          id: `agent-${Date.now()}`,
          type: "agent",
          agent: "system",
          content: `**Agent Team Status:**\n${lines.join("\n")}`,
          timestamp: new Date(),
        }
      } else if (msg.startsWith("/brief")) {
        const data = await api.agentActivity("reporter")
        const brief = data.activities?.find(a => a.action === "daily_brief")
        response = {
          id: `agent-${Date.now()}`,
          type: "agent",
          agent: "reporter",
          content: brief
            ? `**Daily Brief:**\n${brief.summary}`
            : "No daily brief available yet. The Reporter Agent generates them automatically.",
          timestamp: new Date(),
        }
      } else if (msg.startsWith("/risk")) {
        try {
          const data = await api.portfolio()
          const risky = data.positions.filter(p => (p.pnl_pct || 0) < -5)
          response = {
            id: `agent-${Date.now()}`,
            type: "agent",
            agent: "risk_manager",
            content: risky.length
              ? `**Risk Alert:** ${risky.length} position(s) showing losses:\n${risky.map(p => `• ${(p.market_question || p.market_id).slice(0, 40)} — ${(p.pnl_pct || 0).toFixed(1)}%`).join("\n")}`
              : "All positions looking healthy. No risk alerts.",
            timestamp: new Date(),
          }
        } catch {
          response = {
            id: `agent-${Date.now()}`,
            type: "agent",
            agent: "risk_manager",
            content: "No portfolio to monitor. Start trading first!",
            timestamp: new Date(),
          }
        }
      } else {
        response = {
          id: `agent-${Date.now()}`,
          type: "agent",
          agent: "system",
          content: `I understand your request. Available commands:\n• /signals — Latest trading signals\n• /portfolio — Your positions & P&L\n• /agents — Agent team status\n• /brief — Latest daily brief\n• /risk — Risk check on positions\n\nMore capabilities coming soon!`,
          timestamp: new Date(),
        }
      }

      setMessages(prev => [...prev, response])
    } catch {
      setMessages(prev => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          type: "agent",
          agent: "system",
          content: "Something went wrong. Please try again.",
          timestamp: new Date(),
        },
      ])
    } finally {
      setProcessing(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-80px)]">
      <PageHeader title="Agent Workspace" subtitle="Chat with your AI team" />

      <div className="flex-1 flex gap-5 min-h-0">
        {/* Chat area */}
        <div className="flex-1 flex flex-col min-w-0">
          <Card className="flex-1 flex flex-col overflow-hidden p-0 shadow-card shadow-glass">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              <AnimatePresence initial={false}>
                {messages.map((msg) => {
                  const color = msg.agent ? AGENT_COLORS[msg.agent] : undefined
                  return (
                    <motion.div
                      key={msg.id}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={cn(
                        "flex gap-2.5",
                        msg.type === "user" && "justify-end",
                      )}
                    >
                      {msg.type === "agent" && (
                        <div
                          className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 glass-card border border-edge-subtle shadow-inner-glow"
                          style={{ background: `${color}20`, color }}
                        >
                          {msg.agent ? AGENT_ICONS[msg.agent] : <Bot size={14} />}
                        </div>
                      )}
                      <div
                        className={cn(
                          "max-w-[75%] rounded-xl px-3.5 py-2.5 text-sm leading-relaxed border shadow-card",
                          msg.type === "user"
                            ? "glass-card border-accent/35 text-txt-primary bg-surface-raised/35 shadow-glow"
                            : "glass-card border-edge-subtle text-txt-secondary bg-surface-card/50",
                        )}
                      >
                        {msg.type === "agent" && msg.agent && msg.agent !== "system" && (
                          <span className="text-[10px] font-bold font-display tracking-display uppercase block mb-1" style={{ color }}>
                            {msg.agent.replace("_", " ")}
                          </span>
                        )}
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    </motion.div>
                  )
                })}
              </AnimatePresence>
              {processing && (
                <div className="flex gap-2.5">
                  <div className="w-7 h-7 rounded-lg glass-card border border-edge-subtle bg-surface-raised/60 flex items-center justify-center shadow-inner-glow">
                    <Activity size={14} className="text-accent-bright animate-pulse" />
                  </div>
                  <div className="rounded-xl glass-card border border-edge-subtle shadow-card px-4 py-3 bg-surface-raised/40">
                    <span className="text-sm text-txt-muted animate-pulse font-display">Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Quick actions */}
            <div className="px-4 py-2 flex gap-2 flex-wrap border-t border-edge-subtle bg-surface-0/20">
              {QUICK_ACTIONS.map(({ label, prompt }) => (
                <button
                  key={prompt}
                  onClick={() => handleSend(prompt)}
                  className="text-[11px] px-2.5 py-1.5 rounded-lg border border-edge-subtle bg-surface-raised/50 text-txt-muted hover:text-accent-bright hover:border-accent/30 hover:shadow-glass transition-all font-display tracking-display"
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Input */}
            <div className="p-3 border-t border-edge-subtle bg-surface-0/25">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Type a command or ask a question..."
                  className="flex-1 rounded-lg bg-surface-raised/80 border border-edge-subtle px-4 py-2.5 text-sm text-txt-primary placeholder:text-txt-muted/50 outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/35 shadow-inner-glow"
                />
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim() || processing}
                  className="w-10 h-10 rounded-lg bg-accent text-surface-0 flex items-center justify-center shadow-glow hover:shadow-card-hover hover:brightness-110 transition-all disabled:opacity-40 border border-accent-bright/30"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </Card>
        </div>

        {/* Activity sidebar */}
        <div className="hidden lg:block w-[280px] shrink-0">
          <Card className="h-full overflow-hidden flex flex-col p-0 shadow-card shadow-glass">
            <div className="p-3 font-display tracking-display text-xs font-semibold text-txt-muted uppercase border-b border-edge-subtle bg-surface-0/30">
              Live Activity
            </div>
            <div className="flex-1 overflow-y-auto">
              {activityData?.activities?.slice(0, 20).map((act) => {
                const color = AGENT_COLORS[act.agent] || "#888"
                return (
                  <div key={act.id} className="px-3 py-2.5 border-b border-edge-subtle last:border-b-0 hover:bg-surface-raised/30 transition-colors"
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className="w-4 h-4 rounded flex items-center justify-center glass-card border border-edge-subtle" style={{ color }}>
                        {AGENT_ICONS[act.agent]}
                      </span>
                      <span className="text-[10px] font-semibold font-display tracking-display" style={{ color }}>
                        {act.agent_name}
                      </span>
                    </div>
                    <p className="text-[11px] text-txt-muted leading-snug line-clamp-2">
                      {act.summary}
                    </p>
                    <span className="text-[9px] text-txt-muted/60">{timeAgo(act.at)} ago</span>
                  </div>
                )
              })}
              {!activityData?.activities?.length && (
                <div className="p-4 text-center text-xs text-txt-muted font-display">
                  No activity yet
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
