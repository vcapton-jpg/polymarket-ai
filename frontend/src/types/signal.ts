export type SignalCategory =
  | "geopolitics"
  | "politics"
  | "economics"
  | "crypto"
  | "sports"
  | "science"

export type Fact = {
  type: "main" | "risk" | "context"
  icon: string
  title: string
  text: string
}

export type Source = {
  tier: 1 | 2 | 3
  name: string
  detail: string
  minutesAgo: number
}

/**
 * Rich per-article source exposed by GET /api/signals/{id} and
 * /api/signals/{id}/sources. Populated by the Axis-A reasoning pipeline
 * (LLM excerpt + EventNewsLink.relevance_score). Frontend uses this on
 * the detail page alongside the legacy `sources: Source[]` field.
 */
export type SignalSource = {
  newsId: number
  title: string
  url: string
  sourceName: string
  sourceTier: 1 | 2 | 3
  sourceWeight?: number | null
  publishDate?: string | null
  excerpt?: string | null
  relevanceScore?: number | null
  role: "primary" | "supporting"
}

/**
 * Post-resolution learning card for a signal. Populated by the backend once
 * the underlying Polymarket market settles (or the window expires). The
 * frontend renders it on `/signals/:id/outcome` so users can compare the
 * original call to what actually happened, with a one-line lesson.
 *
 * `directionCorrect === null` means the market hasn't resolved yet;
 * `finalPrice`/`basePrice`/`movePct` may be null when unavailable.
 */
export type SignalOutcome = {
  directionCorrect: boolean | null
  finalPrice: number | null
  basePrice: number | null
  movePct: number | null
  learningPoint: string
}

export type TimelineEvent = {
  at: string
  source: string
  type: "news" | "market_move"
  headline?: string | null
  detail?: string | null
}

export type Signal = {
  id: string
  category: SignalCategory
  categoryLabel: string
  createdAt: string
  question: string
  direction: "YES" | "NO"
  marketProbability: number
  windowHours: number
  score: number
  scoreLabel: string
  confidence: "Haute" | "Moyenne" | "Basse"
  urgency: "Haute" | "Moyenne" | "Basse" | "Faible"
  tradability: "Bonne" | "Moyenne" | "Faible"
  catalyst: string
  facts: Fact[]
  sources: Source[]
  lifePercent: number
  polymarketUrl: string
  /** Market thumbnail from Polymarket Gamma API (image field on event/market). */
  image?: string
  reasoning?: string | null
  llmModelVersion?: string | null
  sourceTierMix?: Record<string, number> | null
  detailedSources?: SignalSource[]
  timeline?: TimelineEvent[]
  /** Post-resolution learning card. Backend populates once resolved. */
  outcome?: SignalOutcome | null
}

export type UserProfile = {
  type: "Découvreur" | "Actif" | "Confirmé"
  experience: "Jamais" | "Un peu" | "Régulièrement"
  reaction: "Sors vite" | "J'attends" | "Je renforce"
  budget: "<50€" | "50-200€" | ">200€"
  suggestedSizing: string
}

export type PositionStatus = "tenir" | "surveiller" | "vendre"

export type PositionSource = "manual" | "native"

export type Position = {
  id: string
  signalId: string
  signal: Signal
  /** Direction taken when opening the position — YES or NO only. */
  direction: "YES" | "NO"
  /** Entry price (0–1). */
  entryPrice: number
  /** Current price (0–1). */
  currentPrice: number
  entryDate: string
  status: PositionStatus
  lifePercent: number
  /**
   * Estimated gain in USD (positive or negative). Renamed from "estimatedPnL"
   * in V2 — user-facing wording uses "gain estimé", never "P&L".
   */
  estimatedGain: number
  /** Stake in USD. Polymarket trades in USDC so USD is the canonical unit. */
  stake: number
  resolved: boolean
  correctPrediction: boolean | null
  /** Whether the order was placed through Foresight (native) or recorded manually. */
  source: PositionSource
}

/**
 * Draft of an order being composed in the OrderForm UI (Signal Detail).
 * Actual submission is a backend concern — Cursor wires the CLOB client later.
 */
export type OrderDraft = {
  signalId: string
  direction: "YES" | "NO"
  /** Amount to invest, in USD. */
  amount: number
  /** Price per share (0 to 1), typically the signal's current market probability. */
  pricePerShare: number
  /** amount / pricePerShare */
  estimatedShares: number
  /** shares * 1.00 - amount (if direction resolves true). In USD. */
  estimatedReturn: number
}

export type CategoryDistribution = {
  category: string
  count: number
  percentage: number
}

export type WinRatePoint = {
  date: string
  platform: number
  user: number
}

/** Weekly gain point (USD) for the bar chart on Performance. */
export type GainsOverTimePoint = {
  week: string
  gain: number
}

export type UserWinRateByCategory = {
  category: string
  winRate: number
  signalCount: number
}

export type PerformanceStats = {
  // User first
  userSignalsFollowed: number
  userCorrectPredictions: number
  userWinRate: number
  userBestCategory: string
  userBestCategoryWinRate: number
  /** Estimated net gain in USD. Renamed from userEstimatedPnL in V2. */
  userEstimatedGain: number
  userWinRateByCategory: UserWinRateByCategory[]

  // Telegram
  telegramAlertsReceived: number
  telegramAlertsFollowed: number
  telegramFollowRate: number

  // Platform
  totalSignalsGenerated: number
  platformWinRate: number
  platformAvgScore: number
  avgPipelineDelay: number

  // Charts
  signalsByCategory: CategoryDistribution[]
  winRateOverTime: WinRatePoint[]
  gainsOverTime: GainsOverTimePoint[]
}

/** Shared preference types (duplicated here so consumers don't need to import from lib). */
export type Currency = "USD" | "EUR"
export type Language = "fr" | "en"

export type UserPreferences = {
  currency: Currency
  language: Language
  /** 1 USD = X EUR. Mocked at 0.92 in V2. */
  exchangeRate: number
}

export type LearnSection = {
  id: string
  title: string
  icon: string
  description: string
  content: string
}
