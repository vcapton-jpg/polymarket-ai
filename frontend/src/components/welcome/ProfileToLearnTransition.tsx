/**
 * Cinematic 3-frame bridge from Welcome's profile recap to /apprendre.
 *
 * Plays as a full-screen overlay after the user validates their profile.
 * The recap card (with its pulsing brand-glow) collapses into a small
 * "profile badge" that travels via Framer's `layoutId` continuation into
 * the Apprendre header — see `Apprendre.tsx` for the receiving anchor.
 *
 * Frame timeline (default motion):
 *   F1   0 → 600ms   recap fades, profile badge centers
 *   F2 600 → 1700ms  intro line types in (AnimatedLetters)
 *   F3 1700 → 2900ms LearnDeckPreview slides in (3 cards staggered)
 *   F4 2900ms+       primary CTA visible; auto-advance at 5500ms
 *
 * `useReducedMotion` collapses every duration to ~0 and skips the
 * staggered reveals so a screen-reader user just sees the final state
 * with the CTA, then can click through.
 */
import { useEffect, useState } from "react"
import { motion, useReducedMotion } from "framer-motion"
import { ArrowRight, Sparkles } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { Compass, TrendingUp, Gauge } from "lucide-react"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"

const PROFILE_BADGE_LAYOUT_ID = "welcome-profile-badge"

/** The three sections we preview during the transition. Hand-picked as
 *  the most structurally important entries: what is Polymarket, where the
 *  edge comes from, how the score works. We do not import LEARN_SECTIONS
 *  itself to keep this component decoupled from the data module's
 *  ordering — should those slugs ever be renamed we'd rather get a
 *  visible runtime placeholder than a chained refactor here. */
type DeckCard = {
  number: number
  title: string
  tagline: string
  icon: LucideIcon
  accent: string
}
const DECK: DeckCard[] = [
  {
    number: 1,
    title: "C\u2019est quoi Polymarket\u00A0?",
    tagline: "Tu paries sur des faits, pas sur des tickers.",
    icon: Compass,
    accent: "text-brand-300 bg-brand-500/10 ring-brand-500/30",
  },
  {
    number: 2,
    title: "D\u2019où vient l\u2019opportunité\u00A0?",
    tagline: "Le délai entre l\u2019info qui sort et le prix qui bouge.",
    icon: TrendingUp,
    accent: "text-signal-yes bg-signal-yes/10 ring-signal-yes/30",
  },
  {
    number: 5,
    title: "Comment est calculé le score",
    tagline: "Les variables qui fabriquent le chiffre 0\u2013100.",
    icon: Gauge,
    accent: "text-purple-300 bg-purple-500/10 ring-purple-500/30",
  },
]

const FRAME_AT = {
  badge: 0,
  line: 600,
  deck: 1700,
  cta: 2900,
  // Hard auto-advance — keeps the flow moving for users who don't click.
  // Generous so even a slow reader of the intro line gets to admire the
  // deck preview before being yanked away.
  autoAdvance: 5500,
} as const

const INTRO_LINE = "Maintenant, on te montre comment ça marche."

export function ProfileToLearnTransition({
  profileType,
  onComplete,
}: {
  profileType: string
  onComplete: () => void
}) {
  const reduced = useReducedMotion()
  const [t, setT] = useState(0)

  useEffect(() => {
    if (reduced) {
      // Reduced-motion: skip straight to the final frame so the CTA is
      // immediately interactive. Auto-advance is also disabled — the
      // user explicitly chooses when to move on.
      setT(FRAME_AT.cta)
      return
    }
    const ticks = [FRAME_AT.line, FRAME_AT.deck, FRAME_AT.cta]
    const timers = ticks.map((ms) => window.setTimeout(() => setT(ms), ms))
    const auto = window.setTimeout(onComplete, FRAME_AT.autoAdvance)
    return () => {
      timers.forEach(window.clearTimeout)
      window.clearTimeout(auto)
    }
  }, [reduced, onComplete])

  const showLine = t >= FRAME_AT.line
  const showDeck = t >= FRAME_AT.deck
  const showCta = t >= FRAME_AT.cta

  return (
    <motion.div
      role="dialog"
      aria-label="Bienvenue dans Apprendre"
      // Full-screen black-glass overlay. z-50 so it sits above the
      // Welcome page's own content but below toast notifications.
      className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-obsidian-900/95 backdrop-blur-xl px-6"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: reduced ? 0 : DURATIONS.default, ease: EASE_PREMIUM }}
    >
      {/* F1 — Profile badge. layoutId continuation lands in Apprendre.tsx. */}
      <motion.div
        layoutId={PROFILE_BADGE_LAYOUT_ID}
        className="inline-flex items-center gap-2 rounded-full border border-brand-500/40 bg-brand-500/[0.08] px-4 py-2 shadow-brand-glow"
        initial={{ scale: 0.96, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: reduced ? 0 : DURATIONS.default, ease: EASE_PREMIUM }}
      >
        <Sparkles className="h-3.5 w-3.5 text-brand-400" aria-hidden />
        <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
          Profil
        </span>
        <span className="text-body-sm font-semibold text-ink">{profileType}</span>
      </motion.div>

      {/* F2 — Intro line, typewriter-style fade-in by characters. */}
      <div className="mt-8 min-h-[2.75rem] text-center">
        {showLine && (
          <h2 className="font-display text-[1.5rem] md:text-[1.75rem] font-semibold tracking-tight text-ink text-balance">
            {INTRO_LINE.split("").map((ch, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{
                  duration: reduced ? 0 : 0.18,
                  delay: reduced ? 0 : i * 0.022,
                  ease: EASE_PREMIUM,
                }}
              >
                {ch === " " ? "\u00A0" : ch}
              </motion.span>
            ))}
          </h2>
        )}
      </div>

      {/* F3 — Deck preview: 3 mini cards sliding in from the right,
          staggered. Mirrors what the user is about to see in /apprendre. */}
      <div className="mt-10 w-full max-w-3xl">
        {showDeck && (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {DECK.map((c, i) => (
              <motion.div
                key={c.number}
                initial={{ opacity: 0, x: 40, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                transition={{
                  duration: reduced ? 0 : DURATIONS.expressive,
                  delay: reduced ? 0 : i * 0.12,
                  ease: EASE_PREMIUM,
                }}
                className="rounded-xl border border-line-strong bg-obsidian-850/80 p-4 backdrop-blur"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex h-9 w-9 items-center justify-center rounded-lg ring-1 font-mono text-label-sm font-semibold ${c.accent}`}
                  >
                    {c.number}
                  </span>
                  <c.icon className="h-4 w-4 text-ink-readable" aria-hidden />
                </div>
                <h3 className="mt-3 text-[0.9375rem] font-semibold text-ink leading-snug">
                  {c.title}
                </h3>
                <p className="mt-1 text-body-sm text-ink-muted leading-relaxed">{c.tagline}</p>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* F4 — CTA. Always rendered once shown so the user can click any
          time after F4 lands; the parent `onComplete` is also called by
          the auto-advance timer. */}
      <div className="mt-10 min-h-[3rem]">
        {showCta && (
          <motion.button
            type="button"
            onClick={onComplete}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduced ? 0 : DURATIONS.default, ease: EASE_PREMIUM }}
            className="inline-flex items-center gap-2 rounded-full bg-brand-500 px-6 py-3 text-body-md font-semibold text-obsidian-950 hover:bg-brand-400 transition-premium cursor-pointer shadow-brand-glow"
          >
            Découvrir Apprendre
            <ArrowRight className="h-4 w-4" />
          </motion.button>
        )}
      </div>
    </motion.div>
  )
}

ProfileToLearnTransition.LAYOUT_ID = PROFILE_BADGE_LAYOUT_ID
