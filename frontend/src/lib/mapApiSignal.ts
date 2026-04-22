import type { Fact, Signal, Source } from "@/types/signal"
import { inferSignalCategory } from "@/lib/inferSignalCategory"
import { scoreLabelFor } from "@/lib/utils"

/** Shape returned by GET /api/signals (each row). */
export type ApiSignalRow = {
  id: number
  event_id: number
  market_id: string
  signal_score: number
  signal_strength?: number | null
  trade_quality?: number | null
  direction: string
  confidence_label?: string | null
  urgency_label?: string | null
  tradability_label?: string | null
  market_price_at_signal?: number | null
  score_label?: string | null
  score_explanation?: string | null
  window_estimate?: string | null
  yes_probability_explanation?: string | null
  event_title?: string | null
  market_question?: string | null
  created_at: string
}

export type ApiLlmAnalysis = {
  impact_direction?: string | null
  impact_strength?: number | null
  llm_confidence?: number | null
  specificity_score?: number | null
  catalysts?: string[] | null
  risks?: string[] | null
  reasoning?: string | null
}

export type ApiEventRow = {
  id: number
  event_title: string
  event_summary?: string | null
  unique_sources_count?: number
}

export type ApiSignalDetail = ApiSignalRow & {
  event?: ApiEventRow | null
  analysis?: ApiLlmAnalysis | null
}

function parseWindowHours(raw: string | null | undefined): number {
  if (!raw) return 48
  const s = raw.toLowerCase()
  if (s.includes("month")) return 24 * 30
  if (s.includes("week")) return 24 * 7
  if (s.includes("day")) return 48
  if (s.includes("hour") || s.match(/\b\d+h\b/)) return 6
  return 48
}

function confidenceFr(label: string | null | undefined): "Haute" | "Moyenne" | "Basse" {
  const v = (label || "").toLowerCase()
  if (v === "high") return "Haute"
  if (v === "medium") return "Moyenne"
  return "Basse"
}

function urgencyFr(label: string | null | undefined): "Haute" | "Moyenne" | "Basse" | "Faible" {
  const v = (label || "").toLowerCase()
  if (v === "critical" || v === "high") return "Haute"
  if (v === "medium") return "Moyenne"
  if (v === "low") return "Basse"
  return "Faible"
}

function tradabilityFr(label: string | null | undefined): "Bonne" | "Moyenne" | "Faible" {
  const v = (label || "").toLowerCase()
  if (v === "excellent" || v === "good") return "Bonne"
  if (v === "fair" || v === "medium") return "Moyenne"
  return "Faible"
}

function directionFr(dir: string): "YES" | "NO" {
  const u = dir.toUpperCase()
  if (u === "BUY_NO" || u === "NO" || u.includes("NO")) return "NO"
  return "YES"
}

function scoreLabelFr(raw: string | null | undefined, score: number): string {
  const v = (raw || "").toLowerCase()
  if (v === "strong") return "Signal fort"
  if (v === "moderate") return "Actionnable"
  if (v === "exceptional") return "Exceptionnel"
  if (v === "monitoring" || v === "weak") return "À surveiller"
  return scoreLabelFor(score)
}

function lifePercentFromCreated(createdAt: string): number {
  const hours = (Date.now() - new Date(createdAt).getTime()) / 3_600_000
  const p = Math.max(5, 100 - Math.min(95, hours * 3))
  return Math.round(p)
}

function buildFactsList(row: ApiSignalRow): Fact[] {
  const mainText =
    row.score_explanation?.trim() ||
    row.yes_probability_explanation?.trim() ||
    row.event_title ||
    "Analyse en cours."
  return [
    {
      type: "main",
      icon: "⚡",
      title: "Signal principal",
      text: mainText,
    },
  ]
}

function buildFactsDetail(row: ApiSignalDetail): Fact[] {
  const facts: Fact[] = []
  const reasoning = row.analysis?.reasoning?.trim()
  if (reasoning) {
    facts.push({ type: "main", icon: "⚡", title: "Analyse IA", text: reasoning })
  } else {
    facts.push(...buildFactsList(row))
  }
  const c0 = row.analysis?.catalysts?.[0]
  if (c0) facts.push({ type: "context", icon: "📌", title: "Catalyseur", text: c0 })
  const r0 = row.analysis?.risks?.[0]
  if (r0) facts.push({ type: "risk", icon: "⚠️", title: "Risque identifié", text: r0 })
  return facts.length ? facts : buildFactsList(row)
}

function buildSourcesDetail(row: ApiSignalDetail): Source[] {
  const n = row.event?.unique_sources_count
  if (n != null && n > 0) {
    return [
      {
        tier: 1,
        name: "Sources agrégées",
        detail: `${n} source(s) distincte(s) sur l’événement`,
        minutesAgo: Math.max(1, Math.round((Date.now() - new Date(row.created_at).getTime()) / 60_000)),
      },
    ]
  }
  return []
}

export function mapApiRowToSignal(row: ApiSignalRow): Signal {
  const question = row.market_question || `Signal #${row.id}`
  const { category, categoryLabel } = inferSignalCategory(question, row.event_title)
  const score = Math.round(row.signal_score)
  const catalyst =
    row.event_title?.trim() ||
    row.score_explanation?.slice(0, 220).trim() ||
    "Contexte marché en cours de mise à jour."

  return {
    id: String(row.id),
    category,
    categoryLabel,
    createdAt: row.created_at,
    question,
    direction: directionFr(row.direction),
    marketProbability: row.market_price_at_signal ?? 0.5,
    windowHours: parseWindowHours(row.window_estimate),
    score,
    scoreLabel: scoreLabelFr(row.score_label, score),
    confidence: confidenceFr(row.confidence_label),
    urgency: urgencyFr(row.urgency_label),
    tradability: tradabilityFr(row.tradability_label),
    catalyst,
    facts: buildFactsList(row),
    sources: [],
    lifePercent: lifePercentFromCreated(row.created_at),
    polymarketUrl: `https://polymarket.com/market/${row.market_id}`,
    image: undefined,
  }
}

export function mapApiDetailToSignal(row: ApiSignalDetail): Signal {
  const base = mapApiRowToSignal(row)
  const summary = row.event?.event_summary?.trim()
  const catalyst =
    summary ||
    row.event_title?.trim() ||
    base.catalyst

  return {
    ...base,
    catalyst,
    facts: buildFactsDetail(row),
    sources: buildSourcesDetail(row),
  }
}
