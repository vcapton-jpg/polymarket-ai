import { formatDistanceToNow, format } from "date-fns"
import type { Signal } from "./types"

export function mergeSignalsDedupe(live: Signal[], api: Signal[], max: number): Signal[] {
  const seen = new Set<number>()
  const out: Signal[] = []
  for (const s of [...live, ...api]) {
    if (seen.has(s.id)) continue
    seen.add(s.id)
    out.push(s)
    if (out.length >= max) break
  }
  return out
}

export function timeAgo(date: string | Date): string {
  return formatDistanceToNow(new Date(date), { addSuffix: false })
}

export function formatDate(date: string | Date): string {
  return format(new Date(date), "MMM d, yyyy HH:mm")
}

export function formatYesImpliedPct(price: number | null | undefined): string {
  if (price == null || Number.isNaN(Number(price))) return "--"
  const pct = Math.round(Number(price) * 1000) / 10
  return `${pct}%`
}

export function formatSpreadPp(spread: number | null | undefined): string {
  if (spread == null || Number.isNaN(Number(spread))) return "--"
  return `${(Number(spread) * 100).toFixed(1)} pts`
}

export function formatUsdCompact(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(Number(amount))) return "--"
  const n = Number(amount)
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`
  return `$${Math.round(n).toLocaleString()}`
}

export function formatNumber(n: number | null | undefined): string {
  if (n == null) return "0"
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function scoreColor(score: number): string {
  if (score >= 90) return "#10B981"
  if (score >= 75) return "#F97316"
  if (score >= 60) return "#F59E0B"
  return "#6B7280"
}

export function scoreBarBg(score: number): string {
  if (score >= 90) return "rgba(16,185,129,0.15)"
  if (score >= 75) return "rgba(249,115,22,0.15)"
  if (score >= 60) return "rgba(245,158,11,0.15)"
  return "rgba(107,114,128,0.15)"
}

export function bucketColor(bucket: string): string {
  const map: Record<string, string> = {
    politics: "#818CF8",
    geopolitics: "#F87171",
    economics: "#34D399",
    crypto: "#FBBF24",
    sports: "#60A5FA",
    science: "#A78BFA",
  }
  return map[bucket] ?? "#94A3B8"
}

export function computeEdge(
  direction: string,
  signalStrength: number | null,
  marketPrice: number | null,
): { value: number; label: string; color: string } {
  if (signalStrength == null || marketPrice == null) {
    return { value: 0, label: "N/A", color: "#6B7280" }
  }

  const str = signalStrength / 100
  const p = Number(marketPrice)
  const directionMultiplier =
    direction === "BUY_YES" ? (1 - p) :
    direction === "BUY_NO" ? p : 0

  const raw = str * directionMultiplier * 2
  const value = Math.round(Math.min(100, raw * 100))

  if (value >= 60) return { value, label: "HIGH", color: "#10B981" }
  if (value >= 35) return { value, label: "MED", color: "#F59E0B" }
  return { value, label: "LOW", color: "#6B7280" }
}

export function strengthColor(score: number): string {
  if (score >= 80) return "#10B981"
  if (score >= 60) return "#F97316"
  if (score >= 45) return "#F59E0B"
  return "#6B7280"
}

export function tradeQualityColor(score: number): string {
  if (score >= 80) return "#10B981"
  if (score >= 60) return "#60A5FA"
  if (score >= 40) return "#F59E0B"
  return "#6B7280"
}

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ")
}
