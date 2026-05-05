import { useEffect, useMemo, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { motion, AnimatePresence } from "framer-motion"
import { EASE_PREMIUM, DURATIONS, useMotionConfig } from "@/lib/motion"
import {
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Bookmark,
  CheckCircle2,
  Download,
  Eye,
  EyeOff,
  Inbox,
  Lock,
  Radio,
  TrendingDown,
  TrendingUp,
  UserCircle2,
  Wallet,
  X,
} from "lucide-react"
import { usePublicStats } from "@/hooks/usePublicStats"
import { EMPTY_STAT_PLACEHOLDER, formatStat } from "@/lib/stats"
import { AppShell } from "@/components/layout/AppShell"
import { KPIStat } from "@/components/portfolio/KPIStat"
import { PositionCard } from "@/components/portfolio/PositionCard"
import { PositionCardSkeleton } from "@/components/portfolio/PositionCardSkeleton"
import { HistoryRow } from "@/components/portfolio/HistoryRow"
import {
  MOCK_POSITIONS,
  MOCK_RESOLVED_POSITIONS,
} from "@/data/positions"
import { MOCK_PERFORMANCE } from "@/data/performance"
import { useUserPreferences } from "@/lib/userPreferences"
import { useManualPositions } from "@/lib/useManualPositions"
import { usePerformance } from "@/hooks/usePerformance"
import { useRemotePositions } from "@/hooks/useRemotePositions"
import { hasToken } from "@/lib/api/auth"
import { DemoDataBadge } from "@/components/ui/DemoDataBadge"
import { usePaperPortfolio } from "@/hooks/usePaperPortfolio"
import { XPBadge } from "@/components/gamification/XPBadge"
import {
  computeBadges,
  computeLevel,
  computeXP,
} from "@/lib/gamification"
import { readLearnProgress } from "@/data/learn"

/** When `VITE_USE_MOCKS=1`, layer the bundled demo positions on top of
 *  whatever the API returns so the UI is never empty in showcase mode. */
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"
import { downloadPositionsCSV } from "@/lib/positionsExport"
import { cn } from "@/lib/utils"
import type { Position, UserProfile } from "@/types/signal"
import { STORAGE_KEYS } from "@/lib/storageKeys"
import { useNativePositions } from "@/hooks/useNativePositions"

type HistoryFilter = "all" | "correct" | "incorrect" | "pending"

const FILTERS: Array<{ key: HistoryFilter; labelKey: string }> = [
  { key: "all", labelKey: "portfolio.filters.all" },
  { key: "correct", labelKey: "portfolio.filters.correct" },
  { key: "incorrect", labelKey: "portfolio.filters.incorrect" },
  { key: "pending", labelKey: "portfolio.filters.pending" },
]

export default function Portfolio() {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<HistoryFilter>("all")
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [hideStake, setHideStake] = useState(false)
  // Native (localStorage-backed) positions — consolidated from the
  // 28-line inline subscription that used to live here (audit M8).
  const nativePositions = useNativePositions()
  const [highlightedId, setHighlightedId] = useState<string | null>(null)
  const { data: remote, loading } = useRemotePositions()
  // Performance KPIs in this page (winRate, signalsFollowed, correct)
  // come from the same hook as the Performance page; `isMock` lets us
  // surface the demo banner when the API is unreachable / unauth'd.
  const { stats: performanceStats, isMock: performanceIsMock } = usePerformance()
  const { data: paperPositions = [] } = usePaperPortfolio()

  // Educational gamification — rewards reading Apprendre sections + paper
  // practice + outcome reads. NOT profit. outcomeViews + realTrades are
  // wired to 0 today because their endpoints ship in a later task; the XP
  // formula already accounts for them so the jump is expected, not
  // surprising. learnSectionsRead is read once at mount via the
  // localStorage-backed helper — Apprendre fires a `learn-progress-changed`
  // event when a section is opened, but for now Portfolio is unmounted
  // when the user is reading so a snapshot is enough; revisit if we add a
  // persistent gamification HUD that needs live updates.
  const learnSectionsRead = useMemo(
    () => Object.values(readLearnProgress()).filter(Boolean).length,
    [],
  )
  const xp = computeXP({
    outcomeViews: 0,
    paperTrades: paperPositions.length,
    realTrades: 0,
    learnSectionsRead,
  })
  const level = computeLevel(xp)
  const badges = computeBadges({
    outcomeViews: 0,
    paperTrades: paperPositions.length,
    learnSectionsRead,
  })
  const { formatMoney } = useUserPreferences()
  const { positions: manualPositions } = useManualPositions()
  const location = useLocation()
  const [bannerPositionId, setBannerPositionId] = useState<string | null>(null)

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.profile)
      if (raw) setProfile(JSON.parse(raw))
    } catch {
      // ignore
    }
  }, [])

  // Remote (API) + Native (from OrderForm localStorage, legacy path) +
  // manual (localStorage) + demo mocks (dev only). Remote first so the
  // authenticated user's real trades anchor the top of the list.
  // Dedup by `id` to protect against double-writes if a native position
  // has been synced server-side.
  const activePositions: Position[] = useMemo(() => {
    const list: Position[] = [
      ...remote.positions,
      ...nativePositions,
      ...manualPositions,
    ]
    if (USE_MOCKS) list.push(...MOCK_POSITIONS)
    const seen = new Set<string>()
    return list.filter((p) => {
      if (seen.has(p.id)) return false
      seen.add(p.id)
      return true
    })
  }, [remote.positions, nativePositions, manualPositions])

  const resolvedPositions: Position[] = useMemo(() => {
    const list: Position[] = [...remote.resolved]
    if (USE_MOCKS) list.push(...MOCK_RESOLVED_POSITIONS)
    return list
  }, [remote.resolved])

  const capital = useMemo(
    () => activePositions.reduce((sum, p) => sum + p.stake, 0),
    [activePositions],
  )
  const gain = useMemo(
    () =>
      [...activePositions, ...resolvedPositions].reduce(
        (sum, p) => sum + p.estimatedGain,
        0,
      ),
    [activePositions, resolvedPositions],
  )
  // Read from the live hook so empty/zero states are real, not faked.
  const winRate = Math.round(performanceStats.userWinRate * 100)
  const signalsFollowed = performanceStats.userSignalsFollowed
  const correct = performanceStats.userCorrectPredictions

  const handleExportCSV = () => {
    downloadPositionsCSV([...activePositions, ...resolvedPositions])
  }

  const filteredHistory = useMemo(() => {
    switch (filter) {
      case "correct":
        return resolvedPositions.filter((p) => p.resolved && p.correctPrediction === true)
      case "incorrect":
        return resolvedPositions.filter((p) => p.resolved && p.correctPrediction === false)
      case "pending":
        return resolvedPositions.filter((p) => !p.resolved || p.correctPrediction === null)
      default:
        return resolvedPositions
    }
  }, [filter, resolvedPositions])

  const resolvedCount = resolvedPositions.filter((p) => p.resolved).length
  const isEmpty = activePositions.length === 0 && resolvedPositions.length === 0

  // Scroll to & highlight the position referenced by the URL hash
  // (e.g. `#position-pos_1710000000000` after a successful native order).
  useEffect(() => {
    const hash = location.hash
    if (!hash.startsWith("#position-")) return
    const id = hash.slice("#position-".length)
    if (!id) return
    // wait a tick so the element is mounted
    const raf = window.requestAnimationFrame(() => {
      const el = document.getElementById(`position-${id}`)
      if (!el) return
      el.scrollIntoView({ behavior: "smooth", block: "center" })
      setHighlightedId(id)
    })
    // Show persistent banner — Fix 8
    setBannerPositionId(id)
    return () => window.cancelAnimationFrame(raf)
  }, [location.hash, activePositions.length])

  // Auto-dismiss banner after 30 s; also clear on route change.
  useEffect(() => {
    if (!bannerPositionId) return
    const timer = window.setTimeout(() => setBannerPositionId(null), 30_000)
    return () => window.clearTimeout(timer)
  }, [bannerPositionId])
  useEffect(() => {
    return () => setBannerPositionId(null)
  }, [location.pathname])

  const bannerPosition = useMemo(
    () =>
      bannerPositionId
        ? activePositions.find((p) => p.id === bannerPositionId) ?? null
        : null,
    [bannerPositionId, activePositions],
  )

  useEffect(() => {
    if (!highlightedId) return
    const timer = window.setTimeout(() => setHighlightedId(null), 3000)
    return () => window.clearTimeout(timer)
  }, [highlightedId])

  return (
    <AppShell
      breadcrumb={[{ label: t("portfolio.title") }]}
      liveCount={MOCK_PERFORMANCE.totalSignalsGenerated}
    >
      {/* Page header */}
      <div className="border-b border-line/60 bg-obsidian-900">
        <div className="px-4 pt-6 pb-5 md:px-8 md:pt-8 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">{t("portfolio.eyebrow")}</p>
            <h1 className="font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2.125rem]">
              {t("portfolio.heading")}
            </h1>
            <p className="mt-1 text-[0.9375rem] text-ink-muted">
              <span className="num text-ink">{activePositions.length}</span> positions en cours ·{" "}
              <span className="num text-ink">{resolvedCount}</span> résolues
            </p>
            <div className="mt-3">
              <XPBadge xp={xp} level={level} />
            </div>
          </div>
          {!isEmpty && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setHideStake((v) => !v)}
                aria-pressed={hideStake}
                aria-label={hideStake ? "Afficher les montants" : "Masquer les montants"}
                title={hideStake ? "Afficher les montants" : "Masquer les montants"}
                className="inline-flex h-10 min-w-10 items-center justify-center gap-1.5 rounded-md border border-line bg-obsidian-850/60 px-3 text-body-sm text-ink-muted hover:border-line-strong hover:text-ink transition-premium cursor-pointer"
              >
                {hideStake ? (
                  <EyeOff className="h-4 w-4" aria-hidden />
                ) : (
                  <Eye className="h-4 w-4" aria-hidden />
                )}
                <span className="hidden sm:inline">
                  {hideStake ? "Afficher" : "Masquer"}
                </span>
              </button>
              <button
                type="button"
                onClick={handleExportCSV}
                aria-label="Exporter les positions en CSV"
                title="Exporter en CSV"
                className="inline-flex h-10 items-center gap-1.5 rounded-md border border-line bg-obsidian-850/60 px-3 text-body-sm text-ink-muted hover:border-brand-500/40 hover:text-brand-300 transition-premium cursor-pointer"
              >
                <Download className="h-4 w-4" aria-hidden />
                <span className="hidden sm:inline">Export CSV</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {isEmpty ? (
        <EmptyPortfolio />
      ) : (
        <div className="px-4 py-6 md:px-8 md:py-8 space-y-10">
          {performanceIsMock && (
            <DemoDataBadge
              reason={hasToken() ? "api-error" : "no-auth"}
            />
          )}
          <PositionOpenedBanner
            position={bannerPosition}
            formatMoney={formatMoney}
            onDismiss={() => setBannerPositionId(null)}
          />
          {/* Section 0 — Badges (educational gamification). Earned
              badges are full-opacity, unearned are muted so the set of
              "things left to learn" is visible without feeling pushy. */}
          <section aria-labelledby="badges-heading">
            <h3
              id="badges-heading"
              className="mb-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim"
            >
              Badges
            </h3>
            <div className="flex flex-wrap gap-2">
              {badges.map((b) => (
                <div
                  key={b.id}
                  className={cn(
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs",
                    b.earned
                      ? "bg-signal-yes/10 text-signal-yes border border-signal-yes/30"
                      : "bg-obsidian-850 text-ink-dim border border-line/60 opacity-60",
                  )}
                  title={b.earned ? "Obtenu" : "À débloquer"}
                >
                  <span aria-hidden="true">{b.icon}</span>
                  <span>{b.label}</span>
                </div>
              ))}
            </div>
          </section>

          {/* Section 1 — KPIs */}
          <section>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
              <KPIStat
                label={t("portfolio.kpi.capital")}
                value={capital}
                format={(n) => (hideStake ? "•••" : formatMoney(n))}
                sub={`Sur ${activePositions.length} position${activePositions.length > 1 ? "s" : ""}`}
                icon={<Wallet className="h-3.5 w-3.5" />}
              />
              <KPIStat
                label={t("portfolio.kpi.gain")}
                value={gain}
                format={(n) => (hideStake ? "•••" : formatMoney(n, { signed: true }))}
                tone={gain >= 0 ? "positive" : "negative"}
                sub={t("portfolio.kpi.gainSub")}
                icon={gain >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
              />
              <KPIStat
                label={t("portfolio.kpi.winRate")}
                value={winRate}
                suffix="%"
                tone="brand"
                sub={`${correct}/${signalsFollowed} corrects`}
                icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              />
              <KPIStat
                label={t("portfolio.kpi.followed")}
                value={signalsFollowed}
                sub={t("portfolio.kpi.followedSub")}
                icon={<Radio className="h-3.5 w-3.5" />}
              />
            </div>
          </section>

          {/* Section 2 — Active positions */}
          <section>
            <SectionHeader
              eyebrow={t("portfolio.sections.active.eyebrow")}
              title={`${activePositions.length} position${activePositions.length > 1 ? "s" : ""} active${activePositions.length > 1 ? "s" : ""}`}
              caption={t("portfolio.sections.active.caption")}
            />
            {loading ? (
              <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
                {[0, 1, 2].map((i) => (
                  <PositionCardSkeleton key={i} />
                ))}
              </div>
            ) : activePositions.length > 0 ? (
              <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
                {activePositions.map((p) => (
                  <div
                    key={p.id}
                    id={`position-${p.id}`}
                    className={cn(
                      "rounded-2xl transition-premium",
                      highlightedId === p.id && "ring-2 ring-brand-500/40",
                    )}
                  >
                    <PositionCard position={p} hideStake={hideStake} />
                  </div>
                ))}
              </div>
            ) : (
              <NoActivePositions />
            )}
          </section>

          {/* Section 3 — History */}
          {resolvedPositions.length > 0 && (
            <section>
              <SectionHeader
                eyebrow={t("portfolio.sections.history.eyebrow")}
                title={`${resolvedCount} positions résolues`}
              />
              <div role="radiogroup" aria-label="Filtrer l'historique" className="mb-4 flex flex-wrap gap-1.5">
                {FILTERS.map((f) => (
                  <button
                    key={f.key}
                    type="button"
                    role="radio"
                    aria-checked={filter === f.key}
                    tabIndex={filter === f.key ? 0 : -1}
                    onClick={() => setFilter(f.key)}
                    className={cn(
                      "inline-flex items-center rounded-full border px-3 py-1.5 text-body-sm transition-premium cursor-pointer",
                      filter === f.key
                        ? "border-line-strong bg-obsidian-700 text-ink shadow-inset-line"
                        : "border-line bg-obsidian-850/60 text-ink-muted hover:text-ink hover:border-line-strong",
                    )}
                  >
                    {t(f.labelKey)}
                  </button>
                ))}
              </div>
              <div className="flex flex-col gap-2">
                {filteredHistory.length > 0 ? (
                  filteredHistory.map((p) => (
                    <HistoryRow key={p.id} position={p} hideStake={hideStake} />
                  ))
                ) : (
                  <div className="rounded-lg border border-dashed border-line-strong bg-obsidian-850/40 p-8 text-center text-body-md text-ink-muted">
                    {t("portfolio.emptyFilter")}
                  </div>
                )}
              </div>
            </section>
          )}

          {/* Section 4 — Link to full stats */}
          <section className="flex justify-center pt-2">
            <Link
              to="/performance"
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-obsidian-850/60 px-4 py-2 text-body-sm text-ink-muted hover:border-brand-500/40 hover:text-brand-300 transition-premium"
            >
              <BarChart3 className="h-3.5 w-3.5" aria-hidden />
              Voir tes stats complètes
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </section>

          {/* Section 5 — Profile reminder */}
          <ProfileReminder profile={profile} />
        </div>
      )}
    </AppShell>
  )
}

/* ───────────── Sub-components ───────────── */

function SectionHeader({
  eyebrow,
  title,
  caption,
}: {
  eyebrow: string
  title: string
  caption?: string
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div>
        <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
          {eyebrow}
        </p>
        <h2 className="mt-0.5 font-display text-title-md font-semibold tracking-tight text-ink md:text-[1.375rem]">
          {title}
        </h2>
        {caption && <p className="mt-0.5 text-body-sm text-ink-muted">{caption}</p>}
      </div>
    </div>
  )
}

function ProfileReminder({ profile }: { profile: UserProfile | null }) {
  const profileType = profile?.type ?? "Découvreur"
  const sizing = profile?.suggestedSizing ?? "2\u00A0–\u00A05\u00A0% de ton capital"

  return (
    <motion.section
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line/70 bg-obsidian-850/40 px-5 py-4"
    >
      <div className="flex items-center gap-3">
        <div className="grid h-10 w-10 place-items-center rounded-full border border-brand-500/30 bg-brand-500/10 text-brand-300">
          <UserCircle2 className="h-5 w-5" />
        </div>
        <div>
          <p className="text-body-sm text-ink">
            Profil <span className="font-semibold text-brand-300">{profileType}</span>
          </p>
          <p className="text-label-sm text-ink-muted">
            Mise suggérée : <span className="num text-ink">{sizing}</span>
          </p>
        </div>
      </div>
      <Link
        to="/settings"
        className="inline-flex items-center gap-1 text-body-sm font-medium text-brand-400 hover:text-brand-300 transition-premium"
      >
        Modifier mon profil
        <ArrowRight className="h-3.5 w-3.5" />
      </Link>
    </motion.section>
  )
}

function NoActivePositions() {
  return (
    <div className="rounded-2xl border border-dashed border-line-strong bg-obsidian-850/40 p-8 text-center">
      <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full bg-obsidian-800 text-ink-dim">
        <Inbox className="h-5 w-5" />
      </div>
      <p className="font-display text-[1rem] font-medium text-ink">Aucune position active</p>
      <p className="mx-auto mt-1 max-w-sm text-body-md text-ink-muted">
        Suis un signal depuis le feed pour commencer à tracker tes positions ici.
      </p>
      <Link
        to="/signals"
        className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-brand-500 px-4 py-2 text-body-md font-semibold text-obsidian-900 hover:bg-brand-400 transition-premium"
      >
        Voir les signaux
        <ArrowUpRight className="h-3.5 w-3.5" />
      </Link>
    </div>
  )
}

function EmptyPortfolio() {
  // Legal-PR-3 (B8): live count, no marketing default.
  const { data: publicStats } = usePublicStats()
  const activeTraders = publicStats?.active_traders_week ?? null
  return (
    <div className="px-4 py-16 md:px-8">
      <div className="mx-auto max-w-3xl">
        <div className="rounded-2xl border border-dashed border-line-strong bg-obsidian-850/40 p-8 text-center md:p-10">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-obsidian-800 text-ink-dim">
            <Wallet className="h-6 w-6" />
          </div>
          <h3 className="mb-1 font-display text-lg text-ink">
            Aucune position pour l{"\u2019"}instant
          </h3>
          <p className="text-body-md text-ink-muted">
            Démarre ici{"\u00A0"}{"\u2014"} trois chemins courts selon ton besoin.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
          <ActionCard
            to="/signals"
            title="Voir les signaux actifs"
            subtitle={`Parcours les opportunités détectées aujourd${"\u2019"}hui.`}
            icon={<Radio className="h-4 w-4" />}
          />
          <ActionCard
            to="/apprendre"
            title={"Comprendre en 2\u00A0min"}
            subtitle="9 sections courtes pour maîtriser la plateforme."
            icon={<BookOpen className="h-4 w-4" />}
          />
          <ActionCard
            to="/signals?manual=1"
            title={`J${"\u2019"}ai déjà une position ailleurs`}
            subtitle="Enregistre-la pour la suivre ici."
            icon={<Bookmark className="h-4 w-4" />}
          />
        </div>

        {activeTraders !== null && activeTraders > 0 ? (
          <p className="mt-6 text-center text-body-sm text-ink-muted">
            Tu rejoins{" "}
            <span className="num text-ink">{formatStat(activeTraders)}</span>{" "}
            traders qui utilisent Foresight cette semaine.
          </p>
        ) : (
          <p className="mt-6 text-center text-body-sm text-ink-muted">
            Foresight est en bêta — sois parmi les premiers à utiliser le
            pipeline en conditions réelles.
          </p>
        )}
      </div>
    </div>
  )
}

function ActionCard({
  to,
  title,
  subtitle,
  icon,
}: {
  to: string
  title: string
  subtitle: string
  icon: React.ReactNode
}) {
  return (
    <Link
      to={to}
      className="group flex flex-col gap-2 rounded-xl border border-line-strong bg-obsidian-800 p-5 transition-premium hover:border-brand-500/40 cursor-pointer"
    >
      <div className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-brand-500/30 bg-brand-500/10 text-brand-300">
        {icon}
      </div>
      <p className="font-display text-body-md font-semibold text-ink group-hover:text-brand-300 transition-premium">
        {title}
      </p>
      <p className="text-body-sm text-ink-muted">{subtitle}</p>
      <span className="mt-1 inline-flex items-center gap-1 text-body-sm text-brand-400">
        Continuer
        <ArrowRight className="h-3.5 w-3.5" />
      </span>
    </Link>
  )
}

function PositionOpenedBanner({
  position,
  formatMoney,
  onDismiss,
}: {
  position: Position | null
  formatMoney: (n: number, opts?: { signed?: boolean; decimals?: number }) => string
  onDismiss: () => void
}) {
  const motionConfig = useMotionConfig("default")
  return (
    <AnimatePresence>
      {position && (
        <motion.div
          key={position.id}
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -4 }}
          transition={motionConfig}
          role="status"
          className="flex flex-col gap-3 rounded-xl border border-brand-500/25 bg-brand-500/[0.08] p-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex min-w-0 items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-brand-300" aria-hidden />
            <p className="min-w-0 text-body-md text-ink">
              Position ouverte ·{" "}
              <span className="num font-semibold text-brand-300">
                {formatMoney(position.stake)}
              </span>{" "}
              engagés sur{" "}
              <span className="text-ink">{position.signal.question}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/signals"
              className="inline-flex h-9 items-center gap-1 rounded-md border border-line-strong bg-obsidian-800 px-3 text-body-sm text-ink hover:border-brand-500/40 hover:text-brand-300 transition-premium"
            >
              Voir un autre signal
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
            <Link
              to="/pricing?plan=pro"
              className="inline-flex h-9 items-center gap-1 rounded-md border border-brand-500/40 bg-brand-500/10 px-3 text-body-sm text-brand-300 hover:bg-brand-500/15 transition-premium"
            >
              <Lock className="h-3.5 w-3.5" aria-hidden />
              Activer les alertes Telegram (Pro)
            </Link>
            <button
              type="button"
              onClick={onDismiss}
              aria-label="Fermer"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md text-ink-muted hover:bg-obsidian-800 hover:text-ink transition-premium cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

