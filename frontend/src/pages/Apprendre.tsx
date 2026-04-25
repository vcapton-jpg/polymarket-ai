import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { AnimatePresence, motion, useScroll, useSpring, useReducedMotion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS, STAGGER, fadeInUp } from "@/lib/motion"
import { BookOpen, CheckCircle2, Clock, Sparkles, X } from "lucide-react"
import { AppShell } from "@/components/layout/AppShell"
import { LEARN_SECTIONS, readLearnProgress } from "@/data/learn"
import {
  useProfile,
  getApprendreBannerCopy,
  getContentDepth,
  getTooltipDensity,
} from "@/lib/useProfile"
import { IndexCTA } from "@/components/learn/sections"
import { cn } from "@/lib/utils"
import { STORAGE_KEYS } from "@/lib/storageKeys"
import { ProfileToLearnTransition } from "@/components/welcome/ProfileToLearnTransition"

export const PROFILE_EXPLAINERS: Record<string, string> = {
  Découvreur: "Tu découvres les marchés. On garde les explications simples et visuelles.",
  Actif: "Tu trades déjà. On te donne l’essentiel sans redites.",
  Confirmé: "Tu connais le terrain. On ajoute les détails techniques (algorithme, poids, index vectoriel).",
}

export default function Apprendre() {
  const profile = useProfile()
  const location = useLocation()
  // Set by Welcome.tsx via navigate("/apprendre", { state: { fromWelcome: true } })
  // when the user has just finished the cinematic ProfileToLearnTransition.
  // We use it to (a) render the matching profile badge so Framer's `layoutId`
  // animation can land smoothly, and (b) suppress the Découvreur first-visit
  // overlay — that overlay would feel redundant immediately after the
  // transition's CTA explicitly invited the user in.
  const fromWelcome = Boolean(
    (location.state as { fromWelcome?: boolean } | null)?.fromWelcome,
  )
  const [progress, setProgress] = useState<Record<string, boolean>>({})
  const articleRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const [beginnerCoachOpen, setBeginnerCoachOpen] = useState(false)

  // Beginner (Découvreur) first-visit overlay. Fires only when onboarding is
  // marked "done" AND profile is Découvreur AND we haven't shown it before
  // AND the user did not arrive via the Welcome→Apprendre transition (which
  // already serves as the cinematic onboarding moment).
  useEffect(() => {
    if (fromWelcome) return
    try {
      const onboarding = localStorage.getItem(STORAGE_KEYS.onboarding)
      const alreadyCoached = localStorage.getItem(STORAGE_KEYS.apprendreCoached)
      if (
        onboarding === "done" &&
        profile.type === "Découvreur" &&
        alreadyCoached !== "done"
      ) {
        setBeginnerCoachOpen(true)
      }
    } catch {
      // ignore
    }
  }, [profile.type, fromWelcome])

  const dismissBeginnerCoach = () => {
    try {
      localStorage.setItem(STORAGE_KEYS.apprendreCoached, "done")
    } catch {
      // ignore
    }
    setBeginnerCoachOpen(false)
  }

  // Reading progress: track scroll of the article content. `useScroll` with a
  // target ref gives us 0..1 as the content scrolls past. Smoothed via a
  // spring for a non-jittery fill.
  const { scrollYProgress } = useScroll({
    target: articleRef,
    offset: ["start start", "end end"],
  })
  const scaleX = useSpring(scrollYProgress, {
    stiffness: 120,
    damping: 30,
    mass: 0.3,
  })

  useEffect(() => {
    setProgress(readLearnProgress())
    const refresh = () => setProgress(readLearnProgress())
    window.addEventListener("foresight:learn-progress-changed", refresh)
    window.addEventListener("storage", refresh)
    return () => {
      window.removeEventListener("foresight:learn-progress-changed", refresh)
      window.removeEventListener("storage", refresh)
    }
  }, [])

  const readCount = Object.values(progress).filter(Boolean).length
  const totalCount = LEARN_SECTIONS.length

  return (
    <AppShell breadcrumb={[{ label: "Apprendre" }]}>
      {/* Reading progress bar — 2px, fixed top, scales 0→1 with scroll. */}
      <motion.div
        aria-hidden
        style={{ scaleX, transformOrigin: "0% 50%" }}
        className="fixed left-0 right-0 top-0 z-50 h-[2px] bg-gradient-to-r from-brand-500 via-brand-400 to-brand-300"
      />

      <div ref={articleRef}>
      {/* Header */}
      <div className="border-b border-line/60 bg-obsidian-900">
        <div className="px-4 pt-6 pb-5 md:px-8 md:pt-8">
          <div className="flex flex-wrap items-center gap-2">
            <BookOpen className="h-4 w-4 text-brand-400" aria-hidden />
            <p className="font-mono text-eyebrow uppercase text-brand-400">
              Apprendre
            </p>
            {/* Receiving anchor for the Welcome→Apprendre profile-badge
                continuation. Same `layoutId` as the badge in
                ProfileToLearnTransition; Framer animates it into this header
                slot when the user lands here from the transition. We render
                it unconditionally on first paint when `fromWelcome` so the
                layout animation has a destination element to interpolate to.
                After that the badge stays as a quiet header chip — the
                "Profil" banner below remains the canonical control. */}
            {fromWelcome && (
              <motion.div
                layoutId={ProfileToLearnTransition.LAYOUT_ID}
                className="ml-auto inline-flex items-center gap-2 rounded-full border border-brand-500/40 bg-brand-500/[0.08] px-3 py-1 shadow-brand-glow"
                transition={{ duration: reduced ? 0 : DURATIONS.expressive, ease: EASE_PREMIUM }}
              >
                <Sparkles className="h-3 w-3 text-brand-400" aria-hidden />
                <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
                  Profil
                </span>
                <span className="text-label-sm font-semibold text-ink">
                  {profile.type}
                </span>
              </motion.div>
            )}
          </div>
          <motion.h1
            {...fadeInUp}
            transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
            className="mt-1 font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2.125rem]"
          >
            Comprendre Polymarket, pas à pas
          </motion.h1>
          <motion.p
            {...fadeInUp}
            transition={{
              duration: DURATIONS.default,
              delay: reduced ? 0 : 0.08,
              ease: EASE_PREMIUM,
            }}
            className="mt-1 max-w-2xl text-[0.9375rem] text-ink-muted"
          >
            9 sections courtes pour maîtriser la plateforme, le système de
            détection et le cadre. Pas de vidéos, pas de jargon inutile.
          </motion.p>

          {/* Profile banner */}
          <div className="mt-5 inline-flex max-w-full items-center gap-3 rounded-xl border border-line-strong bg-obsidian-850/60 px-4 py-3">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/15 text-brand-300 ring-1 ring-brand-500/30">
              <BookOpen className="h-3.5 w-3.5" aria-hidden />
            </span>
            <div className="flex-1 text-body-sm">
              <p className="text-ink">
                Profil{" "}
                <span className="font-semibold text-brand-300">
                  {profile.type}
                </span>
              </p>
              <p className="text-ink-muted">
                {getApprendreBannerCopy(profile)}
              </p>
              <p className="mt-1 text-label-sm text-ink-dim">
                {PROFILE_EXPLAINERS[profile.type] ?? PROFILE_EXPLAINERS.Actif}
              </p>
              {/* Expose depth + tooltip density as data attributes so the
                  nested Learn sections can pick them up declaratively. */}
              <span
                hidden
                data-learn-depth={getContentDepth(profile)}
                data-tooltip-density={getTooltipDensity(profile)}
              />
            </div>
            <Link
              to="/welcome"
              className="hidden shrink-0 rounded-md border border-line/80 bg-obsidian-800 px-2.5 py-1 text-label-sm text-ink-muted transition-premium hover:border-line-strong hover:text-ink md:inline-block"
            >
              Changer
            </Link>
          </div>
        </div>
      </div>

      <div className="px-4 py-6 md:px-8 md:py-8 space-y-8">
        {/* Progression eyebrow */}
        <div className="flex items-baseline justify-between gap-3">
          <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
            Progression
          </p>
          <p className="num text-body-sm text-ink-muted">
            <span className="text-ink">{readCount}</span>
            <span className="text-ink-dim"> / {totalCount} lues</span>
          </p>
        </div>

        {/* Grid of 9 cards */}
        <div className="grid gap-3 md:grid-cols-2 md:gap-4 lg:grid-cols-3">
          {LEARN_SECTIONS.map((section, i) => {
            const isRead = Boolean(progress[section.slug])
            const Icon = section.icon
            return (
              <motion.div
                key={section.slug}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.3 }}
                transition={{
                  duration: DURATIONS.default,
                  delay: Math.min(i * STAGGER.default, 0.24),
                  ease: EASE_PREMIUM,
                }}
              >
                <Link
                  to={`/apprendre/${section.slug}`}
                  className="group relative flex h-full flex-col overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 px-5 py-5 transition-premium hover:border-brand-500/40 hover:bg-obsidian-800/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/60"
                >
                  {/* Number + icon */}
                  <div className="mb-4 flex items-center justify-between gap-2">
                    <span
                      className={cn(
                        "inline-flex h-8 w-8 items-center justify-center rounded-full font-mono text-label-sm font-semibold ring-1",
                        section.accentClass,
                      )}
                    >
                      {String(section.number).padStart(2, "0")}
                    </span>
                    <Icon
                      className="h-4 w-4 text-ink-dim transition-premium group-hover:text-ink-muted"
                      aria-hidden
                    />
                  </div>

                  {/* Title + tagline */}
                  <h2 className="mb-1 font-display text-[1rem] font-semibold text-ink md:text-body-lg">
                    {section.title}
                  </h2>
                  <p className="mb-4 flex-1 text-body-sm leading-relaxed text-ink-muted">
                    {section.tagline}
                  </p>

                  {/* Footer meta */}
                  <div className="flex items-center justify-between border-t border-line/60 pt-3 text-label-sm">
                    <span className="inline-flex items-center gap-1 text-ink-dim">
                      <Clock className="h-3 w-3" aria-hidden />
                      {section.readingTimeMinutes} min
                    </span>
                    {isRead ? (
                      <span className="inline-flex items-center gap-1 font-medium text-signal-yes">
                        <CheckCircle2 className="h-3 w-3" aria-hidden />
                        Lu
                      </span>
                    ) : (
                      <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                        À lire →
                      </span>
                    )}
                  </div>
                </Link>
              </motion.div>
            )
          })}
        </div>

        {/* Final CTA */}
        <IndexCTA />
      </div>
      </div>
      <BeginnerApprendreOverlay
        open={beginnerCoachOpen}
        onDismiss={dismissBeginnerCoach}
      />
    </AppShell>
  )
}

/* ───────────── Beginner (Découvreur) overlay ───────────── */

function BeginnerApprendreOverlay({
  open,
  onDismiss,
}: {
  open: boolean
  onDismiss: () => void
}) {
  const navigate = useNavigate()
  const reduced = useReducedMotion()
  const ctaRef = useRef<HTMLButtonElement>(null)

  // Focus the primary CTA on open for keyboard users.
  useEffect(() => {
    if (!open) return
    const t = window.setTimeout(() => ctaRef.current?.focus(), 0)
    return () => window.clearTimeout(t)
  }, [open])

  // Escape to dismiss.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss()
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [open, onDismiss])

  if (!open || typeof document === "undefined") return null

  const handleStart = () => {
    onDismiss()
    // First learn section has slug "polymarket" → «\u00A0C'est quoi Polymarket\u00A0?\u00A0»
    navigate("/apprendre/polymarket")
  }

  const handleSkip = () => {
    onDismiss()
    navigate("/signals")
  }

  return createPortal(
    <AnimatePresence>
      <motion.div
        key="apprendre-coach-root"
        className="fixed inset-0 z-[60] grid place-items-center px-4"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{
          duration: reduced ? 0 : DURATIONS.default,
          ease: EASE_PREMIUM,
        }}
      >
        {/* Backdrop — click dismisses */}
        <button
          type="button"
          aria-label="Fermer l’astuce"
          onClick={onDismiss}
          className="absolute inset-0 bg-obsidian-950/70 backdrop-blur-sm"
        />

        <motion.div
          role="dialog"
          aria-modal="true"
          aria-labelledby="apprendre-coach-title"
          initial={{ opacity: 0, scale: 0.96, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={{
            duration: reduced ? 0 : DURATIONS.expressive,
            ease: EASE_PREMIUM,
          }}
          className="relative w-full max-w-md rounded-2xl border border-brand-500/40 bg-obsidian-850/95 p-6 shadow-elevated backdrop-blur-xl md:p-7"
        >
          <button
            type="button"
            onClick={onDismiss}
            aria-label="Fermer"
            className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-md text-ink-dim hover:bg-obsidian-800 hover:text-ink transition-premium cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>

          <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-brand-500/15 text-brand-300 ring-1 ring-brand-500/30">
            <Sparkles className="h-4 w-4" aria-hidden />
          </span>

          <h2
            id="apprendre-coach-title"
            className="mt-4 font-display text-title-md font-semibold text-ink"
          >
            Avant tes premiers signaux
          </h2>
          <p className="mt-2 text-body-md leading-relaxed text-ink-readable">
            {"Prends 3\u00A0minutes pour comprendre comment ça marche. Commence par le plus important\u00A0:"}
          </p>

          <div className="mt-5 flex flex-col gap-3">
            <button
              ref={ctaRef}
              type="button"
              onClick={handleStart}
              className="inline-flex h-11 items-center justify-center gap-1.5 rounded-md bg-brand-500 px-4 text-body-md font-semibold text-obsidian-900 hover:bg-brand-400 active:bg-brand-600 transition-premium cursor-pointer"
            >
              {"Commencer par «\u00A0C’est quoi Polymarket\u00A0?\u00A0»"}
            </button>
            <button
              type="button"
              onClick={handleSkip}
              className="inline-flex h-9 items-center justify-center rounded-md text-body-sm text-ink-dim hover:text-ink transition-premium cursor-pointer"
            >
              Passer et voir les signaux
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body,
  )
}
