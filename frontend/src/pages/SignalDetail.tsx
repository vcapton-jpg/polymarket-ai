import { useParams, Link, useNavigate } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import {
  ArrowLeft,
  ArrowUpRight,
  Bookmark,
  Check,
  ChevronRight,
  Clock,
  Copy,
  Share2,
  Target,
  Timer,
} from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { AppShell } from "@/components/layout/AppShell"
import {
  CategoryPill,
  DirectionBadge,
  ScoreBadge,
  TierBadge,
} from "@/components/signals/badges"
import { formatOpportunityWindow } from "@/lib/formatWindow"
import { OrderForm } from "@/components/signals/OrderForm"
import { WalletScope } from "@/lib/WalletScope"
import { ManualPositionModal } from "@/components/signals/ManualPositionModal"
import { PoweredByPolymarket } from "@/components/signals/PoweredByPolymarket"
import { WhyThisMatters } from "@/components/signals/WhyThisMatters"
import { SourcesList } from "@/components/signals/SourcesList"
import { SignalTimeline } from "@/components/signals/SignalTimeline"
import { getSignalById, MOCK_SIGNALS } from "@/data/signals"
import { fetchSignalDetailFromApi } from "@/lib/apiSignals"
import type { Signal } from "@/types/signal"

/** Dev-only: mocks instead of real API. */
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"
import { fadeIn } from "@/lib/motion"
import { Button } from "@/components/ui/Button"
import { withBuilderCode } from "@/lib/polymarket"
import {
  cn,
  categoryFallback,
  timeSinceISO,
  scoreLabelFor,
  scoreTone,
  toneForLevel,
  truncate,
  type MetricTone,
} from "@/lib/utils"

export default function SignalDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [signal, setSignal] = useState<Signal | undefined>(undefined)
  const [detailLoading, setDetailLoading] = useState(true)
  const [detailError, setDetailError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) {
      setSignal(undefined)
      setDetailLoading(false)
      return
    }
    // Mocks (dev) or non-numeric legacy ids (SIG-2847) resolve from the
    // bundled mock dataset. Numeric ids (DB primary key) hit the API.
    if (USE_MOCKS || !/^\d+$/.test(id)) {
      setSignal(getSignalById(id))
      setDetailLoading(false)
      setDetailError(null)
      return
    }
    let cancelled = false
    setDetailLoading(true)
    setDetailError(null)
    void fetchSignalDetailFromApi(id)
      .then((s) => {
        if (!cancelled) setSignal(s)
      })
      .catch(() => {
        if (!cancelled) {
          setSignal(undefined)
          setDetailError("Impossible de charger ce signal.")
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [id])
  const [bookmarked, setBookmarked] = useState(false)
  const [copied, setCopied] = useState(false)
  const [manualOpen, setManualOpen] = useState(false)
  const orderFormRef = useRef<HTMLElement>(null)
  const [showStickyCTA, setShowStickyCTA] = useState(false)
  const copiedTimeoutRef = useRef<number | null>(null)
  useEffect(() => {
    return () => {
      if (copiedTimeoutRef.current !== null) window.clearTimeout(copiedTimeoutRef.current)
    }
  }, [])

  useEffect(() => {
    const el = orderFormRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => setShowStickyCTA(!entry.isIntersecting),
      { threshold: 0, rootMargin: "0px 0px -80px 0px" },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [signal])

  if (detailLoading) {
    return (
      <AppShell breadcrumb={[{ label: "Signaux", to: "/signals" }, { label: "…" }]}>
        <div className="container-page py-20 text-ink-muted">Chargement…</div>
      </AppShell>
    )
  }

  if (!signal) {
    return (
      <AppShell breadcrumb={[{ label: "Signaux", to: "/signals" }, { label: "Introuvable" }]}>
        <div className="flex min-h-[60vh] items-center justify-center p-6">
          <div className="text-center">
            <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">404</p>
            <h1 className="font-display text-[1.5rem] font-semibold text-ink">
              Signal introuvable
            </h1>
            {detailError && (
              <p className="mt-2 text-[0.9375rem] text-amber-300/90">{detailError}</p>
            )}
            <p className="mt-2 text-[0.9375rem] text-ink-muted">
              Ce signal a peut-être expiré ou n’existe pas.
            </p>
            <Link to="/signals" className="mt-5 inline-block">
              <Button variant="primary" size="md">
                <ArrowLeft className="h-3.5 w-3.5" />
                Voir tous les signaux
              </Button>
            </Link>
          </div>
        </div>
      </AppShell>
    )
  }

  const isYes = signal.direction === "YES"
  const scoreT = scoreTone(signal.score)
  const scoreL = scoreLabelFor(signal.score)

  // No real resolution field on Signal yet — derive a deterministic mock date
  // (~30 days past createdAt) so the Polymarket eyebrow renders something
  // stable per signal. Formatted in French ("15 mai 2026").
  const resolutionDate = new Date(
    new Date(signal.createdAt).getTime() + 30 * 24 * 60 * 60 * 1000,
  )
  const formattedResolutionDate = resolutionDate.toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  })

  const copyId = () => {
    // writeText returns a promise — swallow rejection (permission denied,
    // non-secure context) so the UI doesn't crash.
    void navigator.clipboard.writeText(signal.id).catch(() => {
      // ignore — clipboard unavailable
    })
    setCopied(true)
    if (copiedTimeoutRef.current !== null) window.clearTimeout(copiedTimeoutRef.current)
    copiedTimeoutRef.current = window.setTimeout(() => {
      copiedTimeoutRef.current = null
      setCopied(false)
    }, 1500)
  }

  // Simulated detection timeline
  const timeline = signal.sources.map((s, i) => ({
    at: s.minutesAgo,
    label: `T-${s.minutesAgo}min`,
    text: `${s.name} · ${s.detail}`,
    tier: s.tier,
    isFirst: i === 0,
  }))

  return (
    <AppShell
      breadcrumb={[
        { label: "Signaux", to: "/signals" },
        { label: `${signal.id} · ${truncate(signal.question, 30)}` },
      ]}
      topbarRight={
        // Sticky action zone — visible without scroll. The primary CTA is
        // INTERNAL: we scroll to the on-page OrderForm so users place orders
        // via our Builder Program integration, not by leaving for polymarket.com.
        // Bookmark stays as a compact secondary; on narrow viewports the
        // label collapses to keep the topbar uncluttered.
        <div className="flex items-center gap-2">
          <button
            onClick={() => setBookmarked((b) => !b)}
            aria-label={bookmarked ? "Retirer des favoris" : "Ajouter aux favoris"}
            className={cn(
              "inline-flex h-9 items-center gap-1.5 rounded-md border px-2.5 sm:px-3 text-[0.8125rem] transition-premium cursor-pointer",
              bookmarked
                ? "border-brand-500/40 bg-brand-500/10 text-brand-300"
                : "border-line-strong bg-obsidian-800 text-ink-muted hover:text-ink hover:border-brand-500/40",
            )}
          >
            <Bookmark className={cn("h-3.5 w-3.5", bookmarked && "fill-current")} />
            <span className="hidden sm:inline">
              {bookmarked ? "Enregistré" : "Enregistrer"}
            </span>
          </button>
          <AnimatePresence>
            {showStickyCTA && (
              <motion.a
                key="sticky-cta"
                href="#order-form"
                className="inline-block"
                {...fadeIn}
                exit={{ opacity: 0 }}
                transition={{ duration: DURATIONS.quick, ease: EASE_PREMIUM }}
              >
                <Button variant="primary" size="md">
                  <span>Parier sur ce marché</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </motion.a>
            )}
          </AnimatePresence>
        </div>
      }
    >
      {/* Life bar at top */}
      <div
        className="h-0.5 bg-gradient-to-r from-brand-500 via-brand-400 to-brand-300"
        style={{ width: `${signal.lifePercent}%` }}
        aria-label={`Opportunité active à ${signal.lifePercent}\u00A0%`}
      />

      {/* Authenticated app page — fills the full available width inside the
          shell (viewport minus sidebar). Text-heavy internal blocks carry
          their own reading-width caps where needed. */}
      <div className="px-4 py-6 md:px-8 md:py-8">
        {/* Back link + partnership badge (top-left affordance) */}
        <div className="mb-5 flex items-center justify-between gap-3">
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-1.5 text-[0.8125rem] text-ink-muted hover:text-ink transition-premium cursor-pointer"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Retour
          </button>
          <PoweredByPolymarket size="sm" />
        </div>

        {/* HERO */}
        <motion.section
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
          className={cn(
            "relative overflow-hidden rounded-2xl border p-6 md:p-8",
            "border-line-strong bg-gradient-to-br",
            isYes
              ? "from-signal-yes/10 via-obsidian-900 to-obsidian-900"
              : "from-signal-no/10 via-obsidian-900 to-obsidian-900",
          )}
        >
          <div
            className={cn(
              "absolute left-0 top-0 h-full w-1",
              isYes
                ? "bg-gradient-to-b from-signal-yes via-signal-yes/80 to-signal-yes/20"
                : "bg-gradient-to-b from-signal-no via-signal-no/80 to-signal-no/20",
            )}
            aria-hidden
          />

          <div className="mb-3 flex flex-wrap items-center gap-2.5">
            <CategoryPill label={categoryFallback(signal.categoryLabel)} />
            <span className="num rounded-md border border-line-strong bg-obsidian-800/60 px-2 py-0.5 text-[0.6875rem] text-ink-muted tracking-wider">
              {signal.id}
            </span>
            <span className="inline-flex items-center gap-1 text-[0.75rem] text-ink-muted">
              <Clock className="h-3 w-3" />
              {timeSinceISO(signal.createdAt)}
            </span>
            <span className="ml-auto inline-flex items-center gap-1 rounded-full border border-line-strong bg-obsidian-800/60 px-2.5 py-0.5 text-[0.6875rem] font-mono tracking-wider text-ink-muted">
              Opportunité active&nbsp;: <span className="num text-brand-300">{signal.lifePercent}&nbsp;%</span>
            </span>
          </div>

          <p className="mb-2 inline-flex items-center gap-2 text-label-sm text-ink-readable">
            <span className="h-1.5 w-1.5 rounded-full bg-[#1652F0]" aria-hidden />
            Marché Polymarket · Résolution {formattedResolutionDate}
          </p>
          <h1 className="mb-5 font-display text-[1.5rem] font-semibold leading-tight tracking-tight text-ink text-balance md:text-[2rem]">
            {signal.question}
          </h1>

          {/* Pills row */}
          <div className="flex flex-wrap items-center gap-2">
            <DirectionBadge direction={signal.direction} size="lg" />
            <PillStat label="Marché" value={`${Math.round(signal.marketProbability * 100)}\u00A0%`} />
            <PillStat label="Agir avant" value={formatOpportunityWindow(signal.windowHours)} icon={<Timer className="h-3 w-3" />} />
            <PillStat label="Détecté" value={"moins de 90\u00A0s"} />
          </div>

          {/* Score tile — score on left, score-meta column in the middle,
              market thumbnail on the right (filling previously empty slot). */}
          <div className="mt-6 grid gap-4 rounded-xl border border-line/80 bg-obsidian-800/40 p-5 sm:grid-cols-[auto_1fr_auto] sm:items-center">
            <div className="flex items-baseline gap-2">
              <motion.span
                layoutId={`score-${signal.id}`}
                className={cn(
                  "num font-display text-5xl font-semibold md:text-6xl",
                  scoreT === "exceptional" && "text-brand-300",
                  scoreT === "strong" && "text-brand-400",
                  scoreT === "actionable" && "text-signal-amber",
                  scoreT === "watch" && "text-ink-muted",
                )}
              >
                {signal.score}
              </motion.span>
              <span className="font-mono text-[0.75rem] uppercase tracking-[0.14em] text-ink-dim">
                / 100
              </span>
            </div>
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <ScoreBadge score={signal.score} label={scoreL} size="md" />
                <span className="text-[0.75rem] text-ink-muted">
                  {scoreT === "exceptional"
                    ? "Très rare — priorité maximale sur ta watchlist."
                    : scoreT === "strong"
                      ? "Alignement sources + catalyseurs · entre dans la fenêtre active."
                      : scoreT === "actionable"
                        ? "Actionnable · à valider avec tes propres analyses."
                        : "À surveiller uniquement · n’entre pas en position."}
                </span>
              </div>
              <div className="relative h-1.5 overflow-hidden rounded-full bg-line/60">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${signal.score}%` }}
                  transition={{ duration: 1, ease: EASE_PREMIUM }}
                  className={cn(
                    "absolute inset-y-0 left-0 rounded-full",
                    scoreT === "exceptional" && "bg-gradient-to-r from-brand-400 to-brand-300",
                    scoreT === "strong" && "bg-brand-500",
                    scoreT === "actionable" && "bg-signal-amber",
                    scoreT === "watch" && "bg-ink-dim",
                  )}
                />
              </div>
            </div>
            {signal.image && (
              <img
                src={signal.image}
                alt=""
                aria-hidden
                className="hidden sm:block h-20 w-20 shrink-0 rounded-xl object-cover border border-line-strong/60"
              />
            )}
          </div>

          {/* Sub-metrics */}
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-3">
            <MetricCard label="Confiance" value={signal.confidence} tone={toneForLevel(signal.confidence)} />
            <MetricCard label="Urgence" value={signal.urgency} tone={toneForLevel(signal.urgency)} />
            <MetricCard label="Tradabilité" value={signal.tradability} tone={toneForLevel(signal.tradability)} />
          </div>

          {/* Primary action — native execution UI (Builder Program).
              id="order-form" is the scroll target for the sticky "Placer un
              ordre" CTA in the topbar. */}
          <section ref={orderFormRef} id="order-form" className="mt-6 scroll-mt-24">
            {/* WalletScope is mounted here (not at the React root) so wagmi
                + viem load only inside the SignalDetail chunk. OrderForm
                calls useWalletSetup, which needs WagmiProvider as an
                ancestor — wrapping at the call site keeps the dependency
                lazy. See lib/WalletScope.tsx for the rationale. */}
            <WalletScope>
              <OrderForm
                signal={signal}
                onManualEntry={() => setManualOpen(true)}
              />
            </WalletScope>
          </section>
        </motion.section>

        {/* WHY THIS MATTERS — LLM reasoning + source-tier mix (auto-hides when missing) */}
        <div className="mt-6">
          <WhyThisMatters
            reasoning={signal.reasoning}
            sourceTierMix={signal.sourceTierMix}
          />
        </div>

        {/* FACTS */}
        <section className="mt-8 grid gap-4 md:grid-cols-2">
          {signal.facts.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: DURATIONS.default, delay: 0.1 + i * 0.08, ease: EASE_PREMIUM }}
              className={cn(
                "rounded-xl border p-5",
                f.type === "main" && "border-brand-500/25 bg-brand-500/[0.04]",
                f.type === "risk" && "border-signal-no/30 bg-signal-no/[0.05]",
                f.type === "context" && "border-line-strong bg-obsidian-850/60",
              )}
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="text-base" aria-hidden>{f.icon}</span>
                <h3 className="font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-brand-400">
                  {f.title}
                </h3>
              </div>
              <p className="text-[0.9375rem] leading-relaxed text-ink/90">{f.text}</p>
            </motion.div>
          ))}

        </section>

        {/* DETECTION TIMELINE — when backend provides a real timeline, render the
            new SignalTimeline; otherwise fall back to the mocked legacy block. */}
        {signal.timeline && signal.timeline.length > 0 ? (
          <section className="mt-10">
            <div className="mb-4">
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Détection</p>
              <h2 className="font-display text-[1.25rem] font-semibold text-ink">
                Pourquoi on t’a sorti ce signal
              </h2>
            </div>
            <SignalTimeline events={signal.timeline} />
          </section>
        ) : (
        <section className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Détection</p>
              <h2 className="font-display text-[1.25rem] font-semibold text-ink">
                Pourquoi on t’a sorti ce signal
              </h2>
            </div>
          </div>

          <div className="relative rounded-xl border border-line-strong bg-obsidian-850/40 p-5 md:p-6">
            <div className="absolute left-[1.875rem] top-6 bottom-6 w-px bg-line-strong md:left-[2.25rem]" />

            <ol className="space-y-5">
              {timeline.map((e) => (
                <li key={e.label + e.text} className="relative flex gap-4">
                  <div
                    className={cn(
                      "relative z-10 grid h-6 w-6 shrink-0 place-items-center rounded-full border text-[0.625rem] font-mono font-semibold mt-0.5",
                      e.isFirst
                        ? "border-brand-500/60 bg-brand-500 text-obsidian-900"
                        : "border-line-strong bg-obsidian-800 text-ink-muted",
                    )}
                  >
                    {e.tier}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="mb-0.5 flex flex-wrap items-center gap-2">
                      <span className="num font-mono text-[0.75rem] font-medium text-brand-300">
                        {e.label}
                      </span>
                      <TierBadge tier={e.tier as 1 | 2 | 3} />
                      {e.isFirst && (
                        <span className="rounded bg-brand-500/15 px-1.5 py-0.5 text-[0.6875rem] font-mono uppercase tracking-wider text-brand-300">
                          Premier
                        </span>
                      )}
                    </div>
                    <p className="text-[0.875rem] text-ink/90">{e.text}</p>
                  </div>
                </li>
              ))}

              <li className="relative flex gap-4">
                <div className="relative z-10 grid h-6 w-6 shrink-0 place-items-center rounded-full border border-brand-400 bg-obsidian-850 text-[0.625rem] font-mono font-semibold text-brand-300 mt-0.5">
                  ★
                </div>
                <div className="flex-1 min-w-0">
                  <div className="mb-0.5 flex flex-wrap items-center gap-2">
                    <span className="num font-mono text-[0.75rem] font-medium text-brand-300">T-0</span>
                    <span className="rounded bg-brand-500/15 px-1.5 py-0.5 text-[0.6875rem] font-mono uppercase tracking-wider text-brand-300">
                      Signal émis
                    </span>
                  </div>
                  <p className="text-[0.875rem] text-ink/90">
                    {signal.sources.length} sources indépendantes alignées · score{" "}
                    <span className="num font-semibold text-ink">{signal.score}</span> ·{" "}
                    direction {signal.direction} détectée.
                  </p>
                </div>
              </li>
            </ol>
          </div>
        </section>
        )}

        {/* SOURCES — prefer rich backend sources when available */}
        {signal.detailedSources && signal.detailedSources.length > 0 ? (
          <section className="mt-10">
            <div className="mb-4">
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Sources</p>
              <h2 className="font-display text-[1.25rem] font-semibold text-ink">
                {signal.detailedSources.length} sources indépendantes
              </h2>
            </div>
            <SourcesList sources={signal.detailedSources} />
          </section>
        ) : (
        <section className="mt-10">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Sources</p>
              <h2 className="font-display text-[1.25rem] font-semibold text-ink">
                {signal.sources.length} sources indépendantes
              </h2>
            </div>
            <div className="hidden sm:flex items-center gap-1.5 text-[0.75rem] text-ink-muted">
              <Target className="h-3.5 w-3.5 text-brand-400" />
              Tier-1&nbsp;:{" "}
              <span className="num font-medium text-ink">
                {signal.sources.filter((s) => s.tier === 1).length}
              </span>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {signal.sources.map((s) => (
              // Source cards are non-interactive mocks — no real target URL
              // exists yet. Rendering as a <div> avoids the `href="#"`
              // anti-pattern (accidental navigation + top-of-page jump) and
              // keeps the layout untouched. Cursor can promote to <a> once
              // the backend attaches per-source URLs.
              <div
                key={s.name + s.minutesAgo}
                aria-disabled="true"
                className="flex items-start gap-3 rounded-xl border border-line-strong bg-obsidian-850/40 p-4"
              >
                <TierBadge tier={s.tier} />
                <div className="flex-1 min-w-0">
                  <div className="mb-0.5 flex items-center gap-2">
                    <p className="font-display font-medium text-ink">
                      {s.name}
                    </p>
                  </div>
                  <p className="text-[0.8125rem] text-ink-muted">{s.detail}</p>
                  <p className="num mt-1 text-[0.6875rem] text-ink-dim tracking-wider">
                    il y a {s.minutesAgo}&nbsp;min
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
        )}

        {/* SECONDARY ACTIONS — share, copy, open raw market */}
        <section className="mt-10 rounded-2xl border border-line-strong bg-obsidian-850/40 p-5 md:p-6">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Outils</p>
              <h2 className="font-display text-[1.25rem] font-semibold text-ink">
                Partager ou ouvrir sur Polymarket
              </h2>
              <p className="mt-1.5 text-[0.875rem] text-ink-muted">
                Passe directement sur le marché Polymarket si tu préfères le voir dans son intégralité.
              </p>
            </div>
            <PoweredByPolymarket size="sm" />
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <a href={withBuilderCode(signal.polymarketUrl)} target="_blank" rel="noreferrer" className="inline-flex">
              <Button variant="outline" size="md">
                Voir le marché sur Polymarket
                <ArrowUpRight className="h-4 w-4" />
              </Button>
            </a>
            <motion.button
              onClick={copyId}
              animate={
                copied
                  ? { scale: [1, 1.04, 1], borderColor: "rgba(11,224,166,0.55)" }
                  : { scale: 1, borderColor: "rgba(255,255,255,0.12)" }
              }
              transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
              className="inline-flex h-10 items-center gap-1.5 overflow-hidden rounded-md border border-line-strong bg-obsidian-800 px-4 text-[0.875rem] text-ink-muted hover:text-ink hover:border-brand-500/40 transition-premium cursor-pointer"
              aria-live="polite"
            >
              <AnimatePresence mode="wait" initial={false}>
                {copied ? (
                  <motion.span
                    key="copied"
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    transition={{ duration: DURATIONS.quick, ease: EASE_PREMIUM }}
                    className="inline-flex items-center gap-1.5 text-brand-300"
                  >
                    <Check className="h-4 w-4 text-brand-400" />
                    Copi{"\u00E9"}{"\u00A0"}{"\u2713"}
                  </motion.span>
                ) : (
                  <motion.span
                    key="copy"
                    initial={{ opacity: 0, y: -6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    transition={{ duration: DURATIONS.quick, ease: EASE_PREMIUM }}
                    className="inline-flex items-center gap-1.5"
                  >
                    <Copy className="h-4 w-4" />
                    Copier {signal.id}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
            <button
              type="button"
              aria-label="Partager le signal"
              className="inline-flex h-10 items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800 px-4 text-[0.875rem] text-ink-muted hover:text-ink hover:border-brand-500/40 transition-premium cursor-pointer"
            >
              <Share2 className="h-4 w-4" />
              Partager
            </button>
          </div>
        </section>

        {/* Disclaimer */}
        <p className="mt-6 text-center text-[0.75rem] leading-relaxed text-ink-dim">
          Signal informatif · Ce contenu n’est pas un conseil en investissement. Les marchés de prédiction
          comportent un risque de perte partielle ou totale. Tu prends la décision finale.
        </p>

        {/* Related signals */}
        <RelatedSignals currentId={signal.id} category={signal.category} />
      </div>

      {/* Manual position modal — opened from OrderForm escape hatch */}
      <ManualPositionModal
        open={manualOpen}
        signal={signal}
        onClose={() => setManualOpen(false)}
      />
    </AppShell>
  )
}

function RelatedSignals({ currentId, category }: { currentId: string; category: string }) {
  const related = MOCK_SIGNALS.filter((s) => s.id !== currentId && s.category === category).slice(0, 2)
  if (related.length === 0) return null

  return (
    <section className="mt-12 border-t border-line/60 pt-8">
      <div className="mb-4">
        <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Autres signaux</p>
        <h2 className="font-display text-[1.25rem] font-semibold text-ink">Dans la même catégorie</h2>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {related.map((s) => (
          <Link
            key={s.id}
            to={`/signals/${s.id}`}
            className="group flex items-start gap-4 rounded-xl border border-line-strong bg-obsidian-850/40 p-4 hover:border-brand-500/30 transition-premium"
          >
            <DirectionBadge direction={s.direction} size="sm" />
            <div className="flex-1 min-w-0">
              <p className="mb-1 text-[0.9375rem] text-ink group-hover:text-brand-300 transition-premium line-clamp-2">
                {s.question}
              </p>
              <div className="flex items-center gap-2 text-[0.75rem] text-ink-muted">
                <ScoreBadge score={s.score} size="sm" label={scoreLabelFor(s.score)} />
                <span className="num text-ink-dim">{s.id}</span>
              </div>
            </div>
            <ArrowUpRight className="h-4 w-4 shrink-0 text-ink-dim group-hover:text-brand-400 transition-premium" />
          </Link>
        ))}
      </div>
    </section>
  )
}

function PillStat({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon?: React.ReactNode
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800/60 px-2.5 py-1.5 text-[0.8125rem]">
      {icon && <span className="text-ink-dim">{icon}</span>}
      <span className="text-ink-dim">{label}</span>
      <span className="num font-semibold text-ink">{value}</span>
    </span>
  )
}

function MetricCard({
  label,
  value,
  tone,
}: {
  label: string
  value: string
  tone: MetricTone
}) {
  const toneCls =
    tone === "positive"
      ? "text-signal-yes"
      : tone === "warning"
        ? "text-signal-amber"
        : tone === "negative"
          ? "text-signal-no"
          : "text-ink"

  return (
    <div className="rounded-lg border border-line/70 bg-obsidian-800/40 px-3.5 py-2.5">
      <p className="mb-0.5 font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-ink-dim">
        {label}
      </p>
      <p className={cn("text-[0.9375rem] font-medium", toneCls)}>{value}</p>
    </div>
  )
}

