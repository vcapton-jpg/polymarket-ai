import type {
  SignalListResponse,
  SignalDetail,
  MarketListResponse,
  EventListResponse,
  AccuracyResponse,
  HealthResponse,
  DashboardKpisResponse,
  SimulatedPnlResponse,
  TrackRecordResponse,
  PortfolioData,
  AgentInfo,
  AgentActivityItem,
  PlanInfo,
} from "./types"

const BASE = "/api"

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`)
  return res.json()
}

export const api = {
  health: () => get<HealthResponse>("/health"),

  signals: (params?: {
    bucket?: string
    min_score?: number
    direction?: string
    limit?: number
    offset?: number
  }) => {
    const q = new URLSearchParams()
    if (params?.bucket) q.set("bucket", params.bucket)
    if (params?.min_score != null) q.set("min_score", String(params.min_score))
    if (params?.direction) q.set("direction", params.direction)
    if (params?.limit) q.set("limit", String(params.limit))
    if (params?.offset != null) q.set("offset", String(params.offset))
    return get<SignalListResponse>(`/signals?${q}`)
  },

  signal: (id: number) => get<SignalDetail>(`/signals/${id}`),

  markets: (params?: {
    category?: string
    active_only?: boolean
    limit?: number
    offset?: number
  }) => {
    const q = new URLSearchParams()
    if (params?.category) q.set("category", params.category)
    if (params?.active_only !== undefined) q.set("active_only", String(params.active_only))
    if (params?.limit) q.set("limit", String(params.limit))
    if (params?.offset) q.set("offset", String(params.offset))
    return get<MarketListResponse>(`/markets?${q}`)
  },

  events: (params?: { bucket?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.bucket) q.set("bucket", params.bucket)
    if (params?.limit) q.set("limit", String(params.limit))
    if (params?.offset) q.set("offset", String(params.offset))
    return get<EventListResponse>(`/events?${q}`)
  },

  accuracy: () => get<AccuracyResponse>("/analytics/accuracy"),

  dashboardKpis: () => get<DashboardKpisResponse>("/analytics/dashboard-kpis"),

  simulatedPnl: (minScore = 60) =>
    get<SimulatedPnlResponse>(`/analytics/simulated-pnl?min_score=${minScore}`),

  trackRecord: () => get<TrackRecordResponse>("/analytics/track-record"),

  // Trading
  portfolio: () => get<PortfolioData>("/trading/portfolio"),
  orders: (status?: string) => {
    const q = new URLSearchParams()
    if (status) q.set("status", status)
    return get<{ orders: unknown[]; total: number }>(`/trading/orders?${q}`)
  },
  placeTrade: async (data: {
    market_id: string
    direction: string
    amount: number
    price?: number
    signal_id?: number
  }) => {
    const res = await fetch(`${BASE}/trading/trade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    })
    return res.json()
  },

  // Agents
  agentsStatus: () => get<{ agents: AgentInfo[] }>("/agents/status"),
  agentActivity: (agent?: string) => {
    const q = agent ? `?agent=${agent}` : ""
    return get<{ activities: AgentActivityItem[] }>(`/agents/activity${q}`)
  },

  // Subscriptions
  plans: () => get<{ plans: Record<string, PlanInfo> }>("/subscriptions/plans"),
  currentPlan: () => get<{ plan: string; details: PlanInfo }>("/subscriptions/current"),

  // Briefs
  briefs: () => get<{ activities: unknown[] }>("/agents/activity?agent=reporter"),
}

export const queryKeys = {
  signals: (p?: Record<string, unknown>) => ["signals", p] as const,
  signal: (id: number) => ["signal", id] as const,
  markets: (p?: Record<string, unknown>) => ["markets", p] as const,
  events: (p?: Record<string, unknown>) => ["events", p] as const,
  accuracy: ["accuracy"] as const,
  health: ["health"] as const,
  dashboardKpis: ["dashboardKpis"] as const,
  simulatedPnl: (minScore: number) => ["simulatedPnl", minScore] as const,
  trackRecord: ["trackRecord"] as const,
  portfolio: ["portfolio"] as const,
  orders: (s?: string) => ["orders", s] as const,
  agentsStatus: ["agentsStatus"] as const,
  agentActivity: (a?: string) => ["agentActivity", a] as const,
  plans: ["plans"] as const,
  currentPlan: ["currentPlan"] as const,
}
