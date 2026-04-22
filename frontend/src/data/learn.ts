import {
  BookOpen,
  Compass,
  Flame,
  Gauge,
  HeartPulse,
  HelpCircle,
  Layers,
  Radio,
  ShieldAlert,
  TrendingUp,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

/**
 * The nine Apprendre sections in their canonical order. Ordering is
 * narrative: from "what is this product?" through to "how do I stay safe?"
 * and finally FAQ. Do not re-order without updating the pagination UX in
 * `LearnSection.tsx` — prev/next rely on this array index.
 */
export type LearnSectionMeta = {
  slug: string
  number: number
  title: string
  tagline: string
  readingTimeMinutes: number
  icon: LucideIcon
  /** Used to tint the numbered chip on the index card. */
  accentClass: string
}

export const LEARN_SECTIONS: LearnSectionMeta[] = [
  {
    slug: "polymarket",
    number: 1,
    title: "C’est quoi Polymarket\u00A0?",
    tagline: "Tu paries sur des faits, pas sur des tickers.",
    readingTimeMinutes: 2,
    icon: Compass,
    accentClass: "text-brand-300 bg-brand-500/10 ring-brand-500/30",
  },
  {
    slug: "opportunite",
    number: 2,
    title: "D’où vient l’opportunité\u00A0?",
    tagline: "Le délai entre l’info qui sort et le prix qui bouge.",
    readingTimeMinutes: 2,
    icon: TrendingUp,
    accentClass: "text-signal-yes bg-signal-yes/10 ring-signal-yes/30",
  },
  {
    slug: "rss",
    number: 3,
    title: "Le flux RSS en 30\u00A0secondes",
    tagline: "Reuters, AP, AFP relus toutes les 45\u00A0secondes.",
    readingTimeMinutes: 1,
    icon: Radio,
    accentClass: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  },
  {
    slug: "tiers",
    number: 4,
    title: "Tier-1, Tier-2, Tier-3 expliqués",
    tagline: "Reuters, blog ou compte X\u00A0: la fiabilité de la source change tout.",
    readingTimeMinutes: 3,
    icon: Layers,
    accentClass: "text-blue-300 bg-blue-500/10 ring-blue-500/30",
  },
  {
    slug: "score",
    number: 5,
    title: "Comment est calculé le score",
    tagline: "Les 6 variables qui fabriquent le chiffre 0–100.",
    readingTimeMinutes: 3,
    icon: Gauge,
    accentClass: "text-purple-300 bg-purple-500/10 ring-purple-500/30",
  },
  {
    slug: "barre-vie",
    number: 6,
    title: "La barre de vie d’un signal",
    tagline: "Verte, orange, rouge\u00A0: quand l’edge s’éteint.",
    readingTimeMinutes: 2,
    icon: HeartPulse,
    accentClass: "text-signal-amber bg-signal-amber/10 ring-signal-amber/30",
  },
  {
    slug: "vendre",
    number: 7,
    title: "Quand vendre\u00A0?",
    tagline: "Take-profit, stop-loss, temps écoulé, news contraire.",
    readingTimeMinutes: 2,
    icon: Flame,
    accentClass: "text-orange-300 bg-orange-500/10 ring-orange-500/30",
  },
  {
    slug: "risques",
    number: 8,
    title: "C’est risqué\u00A0?",
    tagline: "Oui. On te dit où sont les trappes avant que tu tombes dedans.",
    readingTimeMinutes: 2,
    icon: ShieldAlert,
    accentClass: "text-signal-no bg-signal-no/10 ring-signal-no/30",
  },
  {
    slug: "faq",
    number: 9,
    title: "FAQ",
    tagline: "Légalité US, impôts, KYC, dépôt, retrait, support.",
    readingTimeMinutes: 5,
    icon: HelpCircle,
    accentClass: "text-ink bg-obsidian-700 ring-line-strong",
  },
]

export const LEARN_FALLBACK_ICON: LucideIcon = BookOpen

export function findLearnSection(slug: string): LearnSectionMeta | undefined {
  return LEARN_SECTIONS.find((s) => s.slug === slug)
}

export function findLearnSectionIndex(slug: string): number {
  return LEARN_SECTIONS.findIndex((s) => s.slug === slug)
}

/* ───────────── Reading progress ───────────── */

const PROGRESS_KEY = "foresight.learn.progress"

export function readLearnProgress(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(PROGRESS_KEY)
    if (!raw) return {}
    return JSON.parse(raw) as Record<string, boolean>
  } catch {
    return {}
  }
}

export function markLearnSectionRead(slug: string): void {
  const progress = readLearnProgress()
  if (progress[slug]) return
  progress[slug] = true
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify(progress))
    window.dispatchEvent(new Event("foresight:learn-progress-changed"))
  } catch {
    /* ignore quota */
  }
}
