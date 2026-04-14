export const BUCKETS = [
  { value: "geopolitics", label: "Geopolitics", emoji: "\u{1F30D}", color: "#F87171", tw: "cat-geo" },
  { value: "politics", label: "Politics", emoji: "\u{1F3DB}\uFE0F", color: "#818CF8", tw: "cat-politics" },
  { value: "economics", label: "Economics", emoji: "\u{1F4C8}", color: "#34D399", tw: "cat-economics" },
  { value: "crypto", label: "Crypto", emoji: "\u20BF", color: "#FBBF24", tw: "cat-crypto" },
  { value: "sports", label: "Sports", emoji: "\u26BD", color: "#60A5FA", tw: "cat-sports" },
  { value: "science", label: "Science", emoji: "\u{1F52C}", color: "#A78BFA", tw: "cat-science" },
  { value: "other", label: "Other", emoji: "\u{1F310}", color: "#94A3B8", tw: "cat-other" },
] as const

export type BucketValue = (typeof BUCKETS)[number]["value"]

export function getBucket(value: string | null | undefined) {
  if (!value) return BUCKETS[BUCKETS.length - 1]
  const lower = value.toLowerCase()
  return BUCKETS.find((b) => b.value === lower) ?? BUCKETS[BUCKETS.length - 1]
}

export function inferBucketFromQuestion(question: string | null | undefined): BucketValue {
  if (!question) return "other"
  const q = question.toLowerCase()

  const cryptoTerms = ["bitcoin", "btc", "ethereum", "eth", "crypto", "solana", "sol", "token", "blockchain", "defi", "nft", "coinbase", "binance", "altcoin", "stablecoin", "usdc", "usdt", "dogecoin", "doge", "xrp", "ripple", "cardano", "polkadot", "avalanche", "polygon", "matic"]
  if (cryptoTerms.some((t) => q.includes(t))) return "crypto"

  const sportsTerms = ["nba", "nfl", "mlb", "nhl", "premier league", "champions league", "world cup", "super bowl", "championship", "playoff", "finals", "match", "game between", "win the", "medal", "olympic", "tournament", "mvp", "scoring leader", "uefa", "fifa", "tennis", "formula 1", "f1", "grand prix", "boxing", "ufc", "mma"]
  if (sportsTerms.some((t) => q.includes(t))) return "sports"

  const geoTerms = ["war", "invasion", "sanctions", "ceasefire", "peace deal", "nato", "un ", "united nations", "territory", "military", "troops", "missile", "nuclear", "iran", "russia", "ukraine", "china", "taiwan", "north korea", "middle east", "conflict", "annex", "embargo", "diplomacy", "ambassador", "sovereignty"]
  if (geoTerms.some((t) => q.includes(t))) return "geopolitics"

  const politicsTerms = ["president", "election", "vote", "congress", "senate", "democrat", "republican", "governor", "impeach", "cabinet", "minister", "parliament", "legislation", "bill pass", "executive order", "primary", "nominee", "ballot", "polling", "approval rating", "trump", "biden"]
  if (politicsTerms.some((t) => q.includes(t))) return "politics"

  const econTerms = ["gdp", "inflation", "interest rate", "fed ", "federal reserve", "recession", "unemployment", "stock", "s&p", "nasdaq", "dow jones", "market crash", "tariff", "trade deficit", "cpi", "ppi", "oil price", "opec", "commodity"]
  if (econTerms.some((t) => q.includes(t))) return "economics"

  const scienceTerms = ["vaccine", "covid", "disease", "fda", "clinical trial", "space", "nasa", "spacex", "mars", "moon", "ai ", "artificial intelligence", "gpt", "quantum", "genome", "crispr", "research", "discovery", "nobel", "climate"]
  if (scienceTerms.some((t) => q.includes(t))) return "science"

  return "other"
}

export const DIRECTION_CONFIG = {
  YES: { label: "BUY YES", color: "#10B981", bg: "rgba(16,185,129,0.12)" },
  NO: { label: "BUY NO", color: "#EF4444", bg: "rgba(239,68,68,0.12)" },
  BUY_YES: { label: "BUY YES", color: "#10B981", bg: "rgba(16,185,129,0.12)" },
  BUY_NO: { label: "BUY NO", color: "#EF4444", bg: "rgba(239,68,68,0.12)" },
  NEUTRAL: { label: "NEUTRAL", color: "#6B7280", bg: "rgba(107,114,128,0.12)" },
  UNCLEAR: { label: "UNCLEAR", color: "#6B7280", bg: "rgba(107,114,128,0.12)" },
} as const

export const SCORE_TIERS = {
  exceptional: { min: 90, label: "Exceptional", color: "#10B981" },
  strong: { min: 75, label: "Strong", color: "#F97316" },
  moderate: { min: 60, label: "Moderate", color: "#F59E0B" },
  monitoring: { min: 0, label: "Monitoring", color: "#6B7280" },
} as const

export function getScoreTier(score: number) {
  if (score >= 90) return SCORE_TIERS.exceptional
  if (score >= 75) return SCORE_TIERS.strong
  if (score >= 60) return SCORE_TIERS.moderate
  return SCORE_TIERS.monitoring
}

export const CONFIDENCE_CONFIG = {
  high: { label: "High", color: "#10B981" },
  medium: { label: "Medium", color: "#FBBF24" },
  low: { label: "Low", color: "#94A3B8" },
} as const

export const URGENCY_CONFIG = {
  critical: { label: "Critical", color: "#EF4444" },
  high: { label: "High", color: "#F97316" },
  medium: { label: "Medium", color: "#FBBF24" },
  low: { label: "Low", color: "#94A3B8" },
} as const

export const TRADABILITY_CONFIG = {
  excellent: { label: "Excellent", color: "#10B981" },
  good: { label: "Good", color: "#34D399" },
  fair: { label: "Fair", color: "#FBBF24" },
  poor: { label: "Poor", color: "#94A3B8" },
} as const
