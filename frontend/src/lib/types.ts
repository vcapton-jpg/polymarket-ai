export interface Signal {
  id: number
  event_id: number
  market_id: string
  signal_score: number
  signal_strength: number | null
  trade_quality: number | null
  direction: string
  confidence_label: string | null
  urgency_label: string | null
  tradability_label: string | null
  market_price_at_signal: number | null
  score_label: string | null
  score_explanation: string | null
  window_estimate: string | null
  yes_probability_explanation: string | null
  event_title: string | null
  market_question: string | null
  created_at: string
}

export interface SignalOutcome {
  signal_id: number
  price_t5min: number | null
  price_t15min: number | null
  price_t1h: number | null
  price_t24h: number | null
  price_resolved: number | null
  direction_correct: boolean | null
  outcome_label: number | null
  move_t5min_pct: number | null
}

export interface Market {
  market_id: string
  question: string
  description: string | null
  category: string | null
  tags: string[] | null
  end_date: string | null
  active: boolean
  closed: boolean
  volume_24h: number | null
  liquidity: number | null
  best_bid: number | null
  best_ask: number | null
  spread: number | null
  last_trade_price: number | null
  liquidity_pct: number | null
  volume_24h_pct: number | null
  updated_at: string
}

export interface Event {
  id: number
  event_title: string
  event_summary: string | null
  key_entities: string[] | null
  event_type: string | null
  bucket: string | null
  articles_count: number
  unique_sources_count: number
  first_seen: string
  last_seen: string
  processing_status: string
}

export interface LlmAnalysis {
  impact_direction: string | null
  impact_strength: number | null
  llm_confidence: number | null
  specificity_score: number | null
  catalysts: string[] | null
  risks: string[] | null
  reasoning: string | null
}

export interface SignalDetail extends Signal {
  event: Event | null
  market: Market | null
  outcome: SignalOutcome | null
  analysis: LlmAnalysis | null
}

export interface SignalListResponse {
  signals: Signal[]
  total: number
}

export interface MarketListResponse {
  markets: Market[]
  total: number
}

export interface EventListResponse {
  events: Event[]
  total: number
}

export interface AccuracyResponse {
  total_signals: number
  resolved_signals: number
  correct_signals: number
  accuracy_pct: number | null
  by_bucket: Record<string, Record<string, number>>
}

export interface HealthResponse {
  status: string
  version: string
  env: string
}

export interface DashboardKpisResponse {
  total_signals: number
  signals_today: number
  resolved_signals: number
  win_rate: number | null
  wins: number
  losses: number
  best_signal: { signal_id: number; score: number; direction: string } | null
  avg_score: number | null
  streak: number
  streak_type: string
}

export interface SimulatedPnlResponse {
  total_signals: number
  resolved_signals: number
  simulated_pnl_pct: number | null
  win_rate: number | null
  wins: number
  losses: number
  avg_win_move_pct: number | null
  avg_loss_move_pct: number | null
  best_signal: Record<string, unknown> | null
  worst_signal: Record<string, unknown> | null
  by_direction: Record<string, { wins: number; losses: number }>
  by_score_tier: Record<string, { wins: number; losses: number }>
}

// ── Trading types ───────────────────────────────────────────────
export interface PortfolioPosition {
  id: number
  market_id: string
  side: string
  size: number
  entry_price: number
  current_price: number | null
  pnl_pct: number | null
  status: string
  market_question: string | null
}

export interface PortfolioData {
  id: number
  name: string
  total_value: number
  cash_balance: number
  positions: PortfolioPosition[]
  open_orders_count: number
}

export interface TradeOrder {
  id: number
  market_id: string
  side: string
  price: number
  size: number
  order_type: string
  status: string
  polymarket_order_id: string | null
  error_msg: string | null
  created_at: string
  filled_at: string | null
}

// ── Agent types ─────────────────────────────────────────────────
export interface AgentInfo {
  id: string
  name: string
  role: string
  icon: string
  status: string
  total_actions: number
  last_activity: {
    action: string
    summary: string
    at: string
  } | null
}

export interface AgentActivityItem {
  id: number
  agent: string
  agent_name: string
  action: string
  summary: string
  details: Record<string, unknown> | null
  at: string
}

// ── Brief types ─────────────────────────────────────────────────
export interface DailyBriefData {
  id: number
  brief_date: string
  brief_type: string
  content: Record<string, unknown>
  created_at: string
}

// ── Subscription types ──────────────────────────────────────────
export interface PlanInfo {
  name: string
  price: number
  signals_per_day: number
  execution: boolean
  risk_alerts: boolean
  daily_briefs: boolean
  api_access: boolean
}

export interface TrackRecordResponse {
  total_signals: number
  resolved_signals: number
  overall_win_rate: number | null
  weekly: {
    week: string | null
    total_signals: number
    resolved: number
    correct: number
    win_rate: number | null
  }[]
  by_bucket: Record<string, { total: number; resolved: number; correct: number; win_rate: number | null }>
  recent_resolved: {
    signal_id: number
    event_title: string | null
    direction: string
    score: number
    outcome_label: number | null
    direction_correct: boolean | null
    created_at: string
  }[]
}
