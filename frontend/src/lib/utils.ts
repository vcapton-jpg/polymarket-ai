import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Truncate `s` to at most `n` characters, appending `…` if it was trimmed.
 * Trims trailing whitespace before appending the ellipsis so we don't get
 * "word …".
 */
export function truncate(s: string, n: number): string {
  if (s.length <= n) return s
  return `${s.slice(0, n).replace(/\s+$/, "")}…`
}

export function formatMinutesAgo(minutes: number): string {
  if (minutes < 1) return "à l'instant"
  if (minutes < 60) return `il y a ${Math.floor(minutes)} min`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `il y a ${hours}h`
  const days = Math.floor(hours / 24)
  return `il y a ${days}j`
}

export function timeSinceISO(iso: string): string {
  const then = new Date(iso).getTime()
  const diffMin = Math.max(0, (Date.now() - then) / 60_000)
  return formatMinutesAgo(diffMin)
}

export function scoreTone(score: number): "watch" | "actionable" | "strong" | "exceptional" {
  if (score >= 90) return "exceptional"
  if (score >= 75) return "strong"
  if (score >= 60) return "actionable"
  return "watch"
}

export function scoreLabelFor(score: number): string {
  const tone = scoreTone(score)
  return {
    watch: "À surveiller",
    actionable: "Actionnable",
    strong: "Signal fort",
    exceptional: "Exceptionnel",
  }[tone]
}

export function categoryFallback(label: string | undefined): string {
  return label && label.trim().length > 0 ? label : "🌐 Monde"
}

/**
 * Known category emojis. Performance mocks store bare category names
 * (e.g. "Géopolitique") while signals/positions carry emoji-prefixed
 * labels ("🌍 Géopolitique"). This helper normalizes a bare name into
 * the display form used throughout the product.
 */
const CATEGORY_EMOJI: Record<string, string> = {
  Géopolitique: "🌍",
  Politique: "🏛️",
  Économie: "📈",
  Crypto: "₿",
  Sport: "⚽",
  Science: "🔬",
}

export function categoryWithEmoji(category: string): string {
  const emoji = CATEGORY_EMOJI[category]
  return emoji ? `${emoji} ${category}` : category
}

/**
 * Semantic color per category — used for charts + pills so the same
 * taxonomy has a consistent visual identity across the app.
 */
const CATEGORY_COLOR: Record<string, string> = {
  Géopolitique: "#60A5FA", // blue-400
  Politique: "#F59E0B", // amber-500
  Économie: "#22C55E", // green-500
  Crypto: "#F97316", // orange-500
  Sport: "#A855F7", // purple-500
  Science: "#06B6D4", // cyan-500
}

export function categoryColor(category: string, fallback = "#5C6A82"): string {
  return CATEGORY_COLOR[category] ?? fallback
}

/**
 * Map a French qualitative level (Confiance / Urgence / Tradabilité) to a
 * tone token used across SignalCard / SignalDetail / MetricCard. Extracted
 * here so the mapping is authoritative in one place.
 */
export type MetricTone = "positive" | "warning" | "negative" | "neutral"

export function toneForLevel(level: string): MetricTone {
  const l = level.toLowerCase()
  if (l === "haute" || l === "bonne") return "positive"
  if (l === "moyenne") return "warning"
  if (l === "basse" || l === "faible") return "negative"
  return "neutral"
}

/**
 * Shared YYYY-MM-DD helper so date-scoped localStorage keys agree across
 * dailyLimit, TrialBanner, etc. Always reads the browser-local date —
 * this is the user-facing day boundary, not UTC.
 */
export function todayISODate(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, "0")
  const day = String(d.getDate()).padStart(2, "0")
  return `${y}-${m}-${day}`
}
