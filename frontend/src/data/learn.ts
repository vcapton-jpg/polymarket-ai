import {
  BookOpen,
  Compass,
  Flame,
  Gauge,
  HeartPulse,
  HelpCircle,
  Layers,
  Radio,
  ScanText,
  ShieldAlert,
  Scale,
  TrendingUp,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

/**
 * The eleven Apprendre sections in their canonical order, organised into
 * three chapters. Ordering is narrative:
 *
 *   Chapter 1 · Comprendre — what is this product, where does the edge
 *     come from, what feeds it, who do we trust.
 *   Chapter 2 · Décoder — how the 0–100 score is built, how to read a
 *     signal card end-to-end, when does the edge die.
 *   Chapter 3 · Agir — how much to bet, when to sell, what can hurt you,
 *     and the practical FAQ (legality / KYC / taxes / withdrawals).
 *
 * Do NOT re-order sections without:
 *  1. Updating prev/next pagination in `LearnSection.tsx` (uses array
 *     index, but stops at chapter boundaries — see CHAPTERS below).
 *  2. Updating the chapter-grouped index UX in `Apprendre.tsx`.
 *  3. Updating `TOTAL_LEARN_SECTIONS` in `lib/gamification.ts` if the
 *     count changes.
 */
export type ChapterId = 1 | 2 | 3

export type LearnSectionMeta = {
  slug: string
  number: number
  /** Which chapter this section belongs to. */
  chapter: ChapterId
  title: string
  tagline: string
  readingTimeMinutes: number
  icon: LucideIcon
  /** Used to tint the numbered chip on the index card. */
  accentClass: string
}

export type ChapterMeta = {
  id: ChapterId
  /** Compact label used in eyebrows / breadcrumbs. */
  label: string
  /** Long-form heading used on the index. */
  title: string
  /** One-sentence promise displayed under the chapter heading. */
  tagline: string
  /** Brand accent for the chapter divider line. */
  accentClass: string
}

export const CHAPTERS: ChapterMeta[] = [
  {
    id: 1,
    label: "Chapitre 1 · Comprendre",
    title: "Comprendre",
    tagline: "Le produit, l’edge, les sources. Le strict nécessaire avant tout le reste.",
    accentClass: "from-brand-500/60 via-brand-400/30 to-transparent",
  },
  {
    id: 2,
    label: "Chapitre 2 · Décoder",
    title: "Décoder un signal",
    tagline: "Le score, la fiche, la barre de vie. Lire ce qu’on te montre sans deviner.",
    accentClass: "from-purple-500/60 via-purple-400/30 to-transparent",
  },
  {
    id: 3,
    label: "Chapitre 3 · Agir",
    title: "Agir",
    tagline: "Combien miser, quand sortir, comment ne pas se brûler.",
    accentClass: "from-amber-500/60 via-amber-400/30 to-transparent",
  },
]

export const LEARN_SECTIONS: LearnSectionMeta[] = [
  /* ───────── Chapitre 1 · Comprendre ───────── */
  {
    slug: "polymarket",
    number: 1,
    chapter: 1,
    title: "C’est quoi Polymarket\u00A0?",
    tagline: "Tu paries sur des faits, pas sur des tickers.",
    readingTimeMinutes: 2,
    icon: Compass,
    accentClass: "text-brand-300 bg-brand-500/10 ring-brand-500/30",
  },
  {
    slug: "opportunite",
    number: 2,
    chapter: 1,
    title: "D’où vient l’opportunité\u00A0?",
    tagline: "Le délai entre l’info qui sort et le prix qui bouge.",
    readingTimeMinutes: 2,
    icon: TrendingUp,
    accentClass: "text-signal-yes bg-signal-yes/10 ring-signal-yes/30",
  },
  {
    slug: "rss",
    number: 3,
    chapter: 1,
    title: "Le flux RSS en 30\u00A0secondes",
    tagline: "Reuters, AP, AFP relus toutes les 45\u00A0secondes.",
    readingTimeMinutes: 1,
    icon: Radio,
    accentClass: "text-amber-300 bg-amber-500/10 ring-amber-500/30",
  },
  {
    slug: "tiers",
    number: 4,
    chapter: 1,
    title: "Tier-1, Tier-2, Tier-3 expliqués",
    tagline: "Reuters, blog ou compte X\u00A0: la fiabilité de la source change tout.",
    readingTimeMinutes: 3,
    icon: Layers,
    accentClass: "text-blue-300 bg-blue-500/10 ring-blue-500/30",
  },

  /* ───────── Chapitre 2 · Décoder ───────── */
  {
    slug: "score",
    number: 5,
    chapter: 2,
    title: "Comment est calculé le score",
    tagline: "Les 6 variables qui fabriquent le chiffre 0–100.",
    readingTimeMinutes: 3,
    icon: Gauge,
    accentClass: "text-purple-300 bg-purple-500/10 ring-purple-500/30",
  },
  {
    slug: "lire-signal",
    number: 6,
    chapter: 2,
    title: "Lire une fiche signal de A à Z",
    tagline: "Les 4 zones d’une carte signal, et ce que chacune te dit.",
    readingTimeMinutes: 3,
    icon: ScanText,
    accentClass: "text-cyan-300 bg-cyan-500/10 ring-cyan-500/30",
  },
  {
    slug: "barre-vie",
    number: 7,
    chapter: 2,
    title: "La barre de vie d’un signal",
    tagline: "Verte, orange, rouge\u00A0: quand l’edge s’éteint.",
    readingTimeMinutes: 2,
    icon: HeartPulse,
    accentClass: "text-signal-amber bg-signal-amber/10 ring-signal-amber/30",
  },

  /* ───────── Chapitre 3 · Agir ───────── */
  {
    slug: "position-sizing",
    number: 8,
    chapter: 3,
    title: "Combien miser\u00A0?",
    tagline: "La règle des 1–3\u00A0% par signal, et pourquoi tu vas la dépasser au début.",
    readingTimeMinutes: 3,
    icon: Scale,
    accentClass: "text-emerald-300 bg-emerald-500/10 ring-emerald-500/30",
  },
  {
    slug: "vendre",
    number: 9,
    chapter: 3,
    title: "Quand vendre\u00A0?",
    tagline: "Take-profit, stop-loss, temps écoulé, news contraire.",
    readingTimeMinutes: 2,
    icon: Flame,
    accentClass: "text-orange-300 bg-orange-500/10 ring-orange-500/30",
  },
  {
    slug: "risques",
    number: 10,
    chapter: 3,
    title: "C’est risqué\u00A0?",
    tagline: "Oui. On te dit où sont les trappes avant que tu tombes dedans.",
    readingTimeMinutes: 2,
    icon: ShieldAlert,
    accentClass: "text-signal-no bg-signal-no/10 ring-signal-no/30",
  },
  {
    slug: "faq",
    number: 11,
    chapter: 3,
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

/** Returns the chapter metadata for a given chapter id. Throws on unknown
 *  ids — callers are expected to pull the id off a `LearnSectionMeta`,
 *  so an unknown id is a programming error. */
export function getChapter(id: ChapterId): ChapterMeta {
  const found = CHAPTERS.find((c) => c.id === id)
  if (!found) throw new Error(`Unknown chapter id: ${id}`)
  return found
}

/** Sections grouped by chapter, preserving canonical order within each
 *  group. Returned as a stable array of [chapter, sections] tuples so
 *  consumers can render them with a regular `.map()`. */
export function sectionsByChapter(): Array<{
  chapter: ChapterMeta
  sections: LearnSectionMeta[]
}> {
  return CHAPTERS.map((chapter) => ({
    chapter,
    sections: LEARN_SECTIONS.filter((s) => s.chapter === chapter.id),
  }))
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
