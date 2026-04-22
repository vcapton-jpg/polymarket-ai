import type { SignalCategory } from "@/types/signal"

const CRYPTO_TERMS = [
  "bitcoin",
  "btc",
  "ethereum",
  "eth ",
  "crypto",
  "solana",
  " sol ",
  "token",
  "blockchain",
  "defi",
  "nft",
  "coinbase",
  "binance",
]

const SPORTS_TERMS = [
  "nba",
  "nfl",
  "mlb",
  "nhl",
  "premier league",
  "champions league",
  "world cup",
  "super bowl",
  "playoff",
  "playoffs",
  "warriors",
  "lakers",
  "ucl",
  "fifa",
  "tennis",
  "ufc",
  "mma",
  "formula 1",
  " f1 ",
]

const GEO_TERMS = [
  "war",
  "sanctions",
  "ceasefire",
  "nato",
  "military",
  "israel",
  "gaza",
  "iran",
  "russia",
  "ukraine",
  "china",
  "taiwan",
  "lebanon",
  "hamas",
  "hezbollah",
  "invasion",
  "conflict",
  "embassy",
  "diplomat",
]

const POLITICS_TERMS = [
  "president",
  "election",
  "congress",
  "senate",
  "democrat",
  "republican",
  "parliament",
  "minister",
  "trump",
  "biden",
  "harris",
  "impeach",
  "supreme court",
  "scotus",
  "pope",
  "prime minister",
]

const ECON_TERMS = [
  "gdp",
  "inflation",
  "interest rate",
  "fed ",
  "fomc",
  "recession",
  "unemployment",
  "stock",
  "s&p",
  "nasdaq",
  "tariff",
  "cpi ",
  "jobs report",
  "earnings",
  "ecb",
  "yield",
]

const SCIENCE_TERMS = [
  "vaccine",
  "fda ",
  "clinical trial",
  "nasa ",
  "spacex",
  " mars ",
  " ai ",
  "artificial intelligence",
  "quantum",
  "climate",
  "pandemic",
]

function match(hay: string): SignalCategory | null {
  if (CRYPTO_TERMS.some((t) => hay.includes(t))) return "crypto"
  if (SPORTS_TERMS.some((t) => hay.includes(t))) return "sports"
  if (GEO_TERMS.some((t) => hay.includes(t))) return "geopolitics"
  if (POLITICS_TERMS.some((t) => hay.includes(t))) return "politics"
  if (ECON_TERMS.some((t) => hay.includes(t))) return "economics"
  if (SCIENCE_TERMS.some((t) => hay.includes(t))) return "science"
  return null
}

const LABEL: Record<SignalCategory, string> = {
  geopolitics: "🌍 Géopolitique",
  politics: "🏛️ Politique",
  economics: "📈 Économie",
  crypto: "₿ Crypto",
  sports: "⚽ Sport",
  science: "🔬 Science",
}

export function inferSignalCategory(
  question: string | null | undefined,
  eventTitle?: string | null | undefined,
): { category: SignalCategory; categoryLabel: string } {
  const q = question ? ` ${question.toLowerCase()} ` : ""
  const t = eventTitle ? ` ${eventTitle.toLowerCase()} ` : ""
  const fromQ = q ? match(q) : null
  const cat = fromQ ?? (t ? match(t) : null) ?? "politics"
  return { category: cat, categoryLabel: LABEL[cat] }
}
