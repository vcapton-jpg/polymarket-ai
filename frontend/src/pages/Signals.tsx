import { Fragment, useCallback, useEffect, useMemo, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { motion, AnimatePresence } from "framer-motion"
import FocusLock from "react-focus-lock"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { ChevronDown, Filter, RefreshCw, Search, SlidersHorizontal, Sparkles, X } from "lucide-react"
import { AppShell } from "@/components/layout/AppShell"
import { SignalCard } from "@/components/signals/SignalCard"
import { SignalCardSkeleton } from "@/components/signals/SignalCardSkeleton"
import { CoachMark } from "@/components/ui/CoachMark"
import { PaywallChip } from "@/components/ui/PaywallChip"
import { PaywallOverlay } from "@/components/ui/PaywallOverlay"
import { MOCK_SIGNALS } from "@/data/signals"
import { fetchSignalsFromApi } from "@/lib/apiSignals"

/** Dev-only: `VITE_USE_MOCKS=1` forces the mock dataset so the page renders
 *  even when the API is offline. Default is API-first with an error banner
 *  if /api/signals fails. */
const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === "1"
import {
  cleanupOldDailyKeys,
  DAILY_SIGNAL_VIEWED_EVENT,
  FREE_DAILY_LIMIT,
  readDailyCount,
  syncQuotaFromServer,
} from "@/lib/dailyLimit"
import { useIsFreePlan } from "@/hooks/useAuth"
import {
  getAdvancedFiltersExpandedDefault,
  getInitialSort,
  useProfile,
} from "@/lib/useProfile"
import { cn } from "@/lib/utils"
import type { Signal, SignalCategory } from "@/types/signal"
import { SESSION_KEYS, STORAGE_KEYS } from "@/lib/storageKeys"

const ADV_FILTERS_KEY = STORAGE_KEYS.signalsAdvFiltersOpen
const CATEGORY_KEYS: CategoryKey[] = [
  "all",
  "geopolitics",
  "politics",
  "economics",
  "crypto",
  "sports",
]

function isCategoryKey(value: string): value is CategoryKey {
  return (CATEGORY_KEYS as string[]).includes(value)
}
function isDirectionKey(value: string): value is DirectionKey {
  return value === "all" || value === "YES" || value === "NO"
}
function isSortKey(value: string): value is SortKey {
  return value === "recent" || value === "score" || value === "urgent"
}

type CategoryKey = SignalCategory | "all"
type DirectionKey = "all" | "YES" | "NO"
type SortKey = "recent" | "score" | "urgent"

const CATEGORIES: Array<{ key: CategoryKey; label: string }> = [
  { key: "all", label: "Tous" },
  { key: "geopolitics", label: "🌍 Géopolitique" },
  { key: "politics", label: "🏛️ Politique" },
  { key: "economics", label: "📈 Économie" },
  { key: "crypto", label: "₿ Crypto" },
  { key: "sports", label: "⚽ Sport" },
]

const SCORE_STEPS: Array<{ value: number; label: string }> = [
  { value: 0, label: "Tous" },
  { value: 60, label: "60+ · Actionnable" },
  { value: 75, label: "75+ · Signal fort" },
  { value: 90, label: "90+ · Exceptionnel" },
]

const SORTS: Array<{ key: SortKey; label: string }> = [
  { key: "recent", label: "Plus récents" },
  { key: "score", label: "Meilleur score" },
  { key: "urgent", label: "Plus urgent" },
]

const URGENCY_WEIGHT: Record<string, number> = {
  Haute: 3,
  Moyenne: 2,
  Basse: 1,
  Faible: 0,
}

export default function Signals() {
  const profile = useProfile()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()

  // Free plan gating — reactive via useAuth subscriber so the paywall
  // flips the moment a trial expires or a card is attached in another
  // tab. Unauth'd users are treated as Free.
  const isFreePlan = useIsFreePlan()

  // Daily signal consumption counter (localStorage, per-day key). The
  // SignalCard component dispatches `foresight:daily_signal_viewed` on
  // click-through — we re-read on that event to stay in sync.
  const [viewedToday, setViewedToday] = useState<number>(() => readDailyCount())
  useEffect(() => {
    cleanupOldDailyKeys()
    // Pull the authoritative server counter at mount so a user who viewed
    // signals from another device doesn't bypass the paywall here.
    void syncQuotaFromServer()
    const onViewed = () => setViewedToday(readDailyCount())
    window.addEventListener(DAILY_SIGNAL_VIEWED_EVENT, onViewed)
    return () => window.removeEventListener(DAILY_SIGNAL_VIEWED_EVENT, onViewed)
  }, [])

  const [category, setCategory] = useState<CategoryKey>(() => {
    const v = searchParams.get("category")
    return v && isCategoryKey(v) ? v : "all"
  })
  const [minScore, setMinScore] = useState<number>(() => {
    const v = searchParams.get("score")
    const n = v ? parseInt(v, 10) : 0
    return Number.isFinite(n) ? n : 0
  })
  const [direction, setDirection] = useState<DirectionKey>(() => {
    const v = searchParams.get("direction")
    return v && isDirectionKey(v) ? v : "all"
  })
  const [sort, setSort] = useState<SortKey>(() => {
    const v = searchParams.get("sort")
    if (v && isSortKey(v)) return v
    return getInitialSort(profile)
  })
  const [query, setQuery] = useState("")
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [apiSignals, setApiSignals] = useState<Signal[]>([])
  const [apiTotal, setApiTotal] = useState(0)
  const [apiLoading, setApiLoading] = useState(true)
  const [apiError, setApiError] = useState<string | null>(null)

  const loadSignals = useCallback(async () => {
    if (USE_MOCKS) {
      setApiSignals(MOCK_SIGNALS)
      setApiTotal(MOCK_SIGNALS.length)
      setApiLoading(false)
      setApiError(null)
      return
    }
    setApiLoading(true)
    setApiError(null)
    try {
      // Backend accepts "YES"/"NO" natively (it normalises legacy BUY_* too).
      const dirParam = direction === "all" ? undefined : direction
      const { signals, total } = await fetchSignalsFromApi({
        limit: 100,
        min_score: minScore > 0 ? minScore : undefined,
        direction: dirParam,
      })
      setApiSignals(signals)
      setApiTotal(total)
    } catch (e) {
      setApiSignals([])
      setApiTotal(0)
      setApiError(e instanceof Error ? e.message : "Impossible de charger les signaux")
    } finally {
      setApiLoading(false)
    }
  }, [minScore, direction])

  useEffect(() => {
    void loadSignals()
  }, [loadSignals])

  // Close mobile filters drawer on Escape.
  useEffect(() => {
    if (!filtersOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFiltersOpen(false)
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  }, [filtersOpen])

  // First-visit coach-mark on the first signal card. Gated by
  // `foresight.first_signal_seen` in localStorage — set to "true" on
  // dismiss (X, Escape) or when the user clicks the card.
  const [coachOpen, setCoachOpen] = useState(false)
  useEffect(() => {
    if (typeof window === "undefined") return
    try {
      const seen = window.localStorage.getItem(STORAGE_KEYS.firstSignalSeen)
      const onboarded = window.localStorage.getItem(STORAGE_KEYS.onboarding)
      if (seen !== "true" && onboarded) {
        // Small delay to let the first card mount + layout settle.
        const t = window.setTimeout(() => setCoachOpen(true), 250)
        return () => window.clearTimeout(t)
      }
    } catch {
      // ignore
    }
  }, [])
  const dismissCoach = () => {
    setCoachOpen(false)
    try {
      window.localStorage.setItem(STORAGE_KEYS.firstSignalSeen, "true")
    } catch {
      // ignore
    }
  }

  // Session-only banner for users who skipped onboarding. Flag written by
  // Welcome.tsx is `foresight.onboarding === "skipped"`. Dismissal lives
  // in `sessionStorage` so it resets on a new session.
  const [skipBannerOpen, setSkipBannerOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false
    try {
      const skipped = window.localStorage.getItem(STORAGE_KEYS.onboarding) === "skipped"
      const dismissed =
        window.sessionStorage.getItem(SESSION_KEYS.skipBannerDismissed) === "true"
      return skipped && !dismissed
    } catch {
      return false
    }
  })
  const dismissSkipBanner = () => {
    setSkipBannerOpen(false)
    try {
      window.sessionStorage.setItem(SESSION_KEYS.skipBannerDismissed, "true")
    } catch {
      // ignore
    }
  }

  // Advanced filters disclosure: persisted in localStorage. On first visit,
  // seed from profile + viewport. Desktops ≥ 1200px with a "Confirmé" profile
  // start expanded; otherwise collapsed.
  const [advFiltersOpen, setAdvFiltersOpen] = useState<boolean>(() => {
    if (typeof window === "undefined") return false
    const stored = window.localStorage.getItem(ADV_FILTERS_KEY)
    if (stored === "true") return true
    if (stored === "false") return false
    const wideEnough = window.innerWidth >= 1200
    return wideEnough && getAdvancedFiltersExpandedDefault(profile)
  })

  useEffect(() => {
    if (typeof window === "undefined") return
    window.localStorage.setItem(ADV_FILTERS_KEY, advFiltersOpen ? "true" : "false")
  }, [advFiltersOpen])

  // Sync filters → URL (replace to avoid polluting history on every click).
  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    if (category !== "all") next.set("category", category)
    else next.delete("category")
    if (direction !== "all") next.set("direction", direction)
    else next.delete("direction")
    if (minScore > 0) next.set("score", String(minScore))
    else next.delete("score")
    next.set("sort", sort)
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true })
    }
  }, [category, direction, minScore, sort, searchParams, setSearchParams])

  const filtered = useMemo(() => {
    const base = apiError ? [...MOCK_SIGNALS] : [...apiSignals]
    let list = [...base]
    if (category !== "all") list = list.filter((s) => s.category === category)
    if (minScore > 0) list = list.filter((s) => s.score >= minScore)
    if (direction !== "all") list = list.filter((s) => s.direction === direction)
    if (query.trim()) {
      const q = query.toLowerCase()
      list = list.filter(
        (s) => s.question.toLowerCase().includes(q) || s.catalyst.toLowerCase().includes(q),
      )
    }

    if (sort === "recent") {
      list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    } else if (sort === "score") {
      list.sort((a, b) => b.score - a.score)
    } else if (sort === "urgent") {
      list.sort((a, b) => (URGENCY_WEIGHT[b.urgency] ?? 0) - (URGENCY_WEIGHT[a.urgency] ?? 0))
    }

    return list
  }, [apiSignals, apiError, category, minScore, direction, sort, query])

  const activeFilterCount =
    (category !== "all" ? 1 : 0) + (minScore > 0 ? 1 : 0) + (direction !== "all" ? 1 : 0)

  const isLimitHit = isFreePlan && viewedToday >= FREE_DAILY_LIMIT
  const isScore90Paywall = isFreePlan && minScore === 90

  // For the Score 90+ FOMO subtitle we want the raw count of 90+ signals in
  // the mock dataset this week — independent of other active filters.
  const score90Count = useMemo(() => {
    const base = apiError ? MOCK_SIGNALS : apiSignals
    return base.filter((s) => s.score >= 90).length
  }, [apiSignals, apiError])

  const goToPricing = () => navigate("/pricing?plan=pro")

  const handleRefresh = () => {
    setRefreshing(true)
    void loadSignals().finally(() => {
      setTimeout(() => setRefreshing(false), 300)
    })
  }

  const resetFilters = () => {
    setCategory("all")
    setMinScore(0)
    setDirection("all")
    setQuery("")
  }

  return (
    <AppShell
      breadcrumb={[{ label: "Signaux" }]}
      liveCount={apiTotal > 0 ? apiTotal : apiSignals.length || MOCK_SIGNALS.length}
      topbarRight={
        <button
          onClick={handleRefresh}
          aria-busy={refreshing}
          className="inline-flex h-9 items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800 px-3 text-body-sm text-ink-muted hover:text-ink hover:border-brand-500/40 transition-premium cursor-pointer"
        >
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} />
          Rafraîchir
        </button>
      }
    >
      {/* Page header */}
      <div className="border-b border-line/60 bg-obsidian-900">
        <div className="px-4 pt-6 pb-5 md:px-8 md:pt-8">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">Signaux</p>
              <h1 id="signals-h1" className="font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2.125rem]">
                {filtered.length > 0
                  ? `${filtered.length} opportunit${filtered.length > 1 ? "és" : "é"} détect${filtered.length > 1 ? "ées" : "ée"}`
                  : "Aucun signal actif"}
              </h1>
              <p className="mt-1 text-[0.9375rem] text-ink-muted">
                <span className="num text-ink">{filtered.length}</span> opportunité{filtered.length > 1 ? "s" : ""} · triée{filtered.length > 1 ? "s" : ""} par{" "}
                <span className="text-ink">{SORTS.find((s) => s.key === sort)?.label.toLowerCase()}</span>. Tu décides, toujours.
              </p>
            </div>

            {/* Search */}
            <div className="relative w-full md:w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-ink-dim" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Rechercher un marché…"
                aria-label="Rechercher dans les signaux"
                className="h-10 w-full rounded-md border border-line-strong bg-obsidian-800 pl-9 pr-9 text-body-md text-ink placeholder:text-ink-dim focus:outline-none focus:border-brand-500/40 focus:ring-2 focus:ring-brand-500/20"
              />
              {query && (
                <button
                  onClick={() => setQuery("")}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 grid h-7 w-7 place-items-center rounded text-ink-dim hover:text-ink hover:bg-obsidian-700 cursor-pointer"
                  aria-label="Effacer la recherche"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Desktop filter row */}
          <div className="hidden md:flex items-center gap-3 flex-wrap">
            {/* Categories */}
            <div className="flex items-center gap-1 overflow-x-auto">
              {CATEGORIES.map((c) => (
                <FilterPill
                  key={c.key}
                  active={category === c.key}
                  onClick={() => setCategory(c.key)}
                >
                  {c.label}
                </FilterPill>
              ))}
            </div>

            <Divider />

            <button
              type="button"
              onClick={() => setAdvFiltersOpen((v) => !v)}
              aria-expanded={advFiltersOpen}
              aria-controls="adv-filters-panel"
              className="inline-flex items-center gap-1.5 rounded-md border border-line bg-obsidian-850/60 px-2.5 py-1 text-label-sm text-ink-muted hover:text-ink hover:border-line-strong transition-premium cursor-pointer"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Filtres avancés
              <ChevronDown
                className={cn(
                  "h-3.5 w-3.5 transition-transform",
                  advFiltersOpen && "rotate-180",
                )}
              />
            </button>

            {advFiltersOpen && (
              <>
                <Divider />

                {/* Catalyseur (score-based filter) — renamed from "Score"
                    to reflect the L&T framing: the number measures how
                    strong the news catalyst is, not a grade. */}
                <div id="adv-filters-panel" className="flex items-center gap-1.5">
                  <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Catalyseur</span>
                  {SCORE_STEPS.map((s) => (
                    <FilterPill
                      key={s.value}
                      active={minScore === s.value}
                      onClick={() => setMinScore(s.value)}
                      size="sm"
                    >
                      {s.label}
                      {s.value === 90 && <PaywallChip />}
                    </FilterPill>
                  ))}
                </div>

                <Divider />

                {/* Direction */}
                <div className="flex items-center gap-1.5">
                  <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Direction</span>
                  <FilterPill active={direction === "all"} onClick={() => setDirection("all")} size="sm">
                    Tous
                  </FilterPill>
                  <FilterPill
                    active={direction === "YES"}
                    onClick={() => setDirection("YES")}
                    size="sm"
                    tone="yes"
                  >
                    ▲ YES
                  </FilterPill>
                  <FilterPill
                    active={direction === "NO"}
                    onClick={() => setDirection("NO")}
                    size="sm"
                    tone="no"
                  >
                    ▼ NO
                  </FilterPill>
                </div>
              </>
            )}

            <div className="flex-1" />

            {/* Sort */}
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Tri</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as SortKey)}
                className="h-8 rounded-md border border-line-strong bg-obsidian-800 px-2.5 text-body-sm text-ink focus:outline-none focus:border-brand-500/40 cursor-pointer"
              >
                {SORTS.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Mobile filter trigger */}
          <div className="flex md:hidden items-center gap-2">
            <button
              onClick={() => setFiltersOpen(true)}
              className="inline-flex flex-1 items-center justify-center gap-2 rounded-md border border-line-strong bg-obsidian-800 px-3 py-2.5 text-body-md text-ink cursor-pointer"
            >
              <SlidersHorizontal className="h-4 w-4" />
              Filtres
              {activeFilterCount > 0 && (
                <span className="num ml-1 grid h-5 min-w-5 place-items-center rounded-full bg-brand-500 px-1.5 text-label-xs font-semibold text-obsidian-900">
                  {activeFilterCount}
                </span>
              )}
            </button>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              className="h-[42px] rounded-md border border-line-strong bg-obsidian-800 px-3 text-body-md text-ink focus:outline-none cursor-pointer"
            >
              {SORTS.map((s) => (
                <option key={s.key} value={s.key}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>

          {/* Active filters summary */}
          {activeFilterCount > 0 && (
            <div className="mt-3 flex items-center gap-2 text-label-sm text-ink-muted">
              <Filter className="h-3.5 w-3.5" />
              {activeFilterCount} filtre{activeFilterCount > 1 ? "s" : ""} actif{activeFilterCount > 1 ? "s" : ""}
              <button
                onClick={resetFilters}
                className="text-brand-400 hover:text-brand-300 underline decoration-line-strong underline-offset-2 cursor-pointer"
              >
                Réinitialiser
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Session-only banner — onboarding skipped */}
      {skipBannerOpen && (
        <div className="px-4 pt-4 md:px-8">
          <div
            role="status"
            className="flex items-center gap-2.5 rounded-lg border border-brand-500/20 bg-brand-500/5 px-3 py-2.5 text-body-sm text-ink"
          >
            <Sparkles className="h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden />
            <span className="flex-1">
              Profil par défaut actif.{" "}
              <Link
                to="/settings#section-profil"
                className="text-brand-400 hover:text-brand-300 underline decoration-line-strong underline-offset-2"
              >
                Calibre tes alertes en 30&nbsp;sec →
              </Link>
            </span>
            <button
              type="button"
              onClick={dismissSkipBanner}
              aria-label="Fermer le rappel"
              className="grid h-7 w-7 place-items-center rounded text-ink-dim hover:text-ink hover:bg-obsidian-800 cursor-pointer"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Grid */}
      <section aria-labelledby="signals-h1" className="px-4 py-6 md:px-8 md:py-8">
        {apiError && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-body-sm text-ink"
          >
            <span className="font-medium text-amber-200">API indisponible.</span>{" "}
            <span className="text-ink-muted">{apiError}</span>
            {" · "}
            <span className="text-ink-muted">Affichage des données de démo.</span>
          </div>
        )}
        {apiLoading && !filtered.length ? (
          <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
            {Array.from({ length: 6 }).map((_, i) => (
              <SignalCardSkeleton key={i} />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState onReset={resetFilters} />
        ) : (
          <motion.div layout className="grid gap-4 md:gap-5 xl:grid-cols-2">
            <AnimatePresence mode="popLayout">
              {filtered.map((s, i) => {
                // Score 90+ wholesale gate for Free users: every matched
                // card renders blurred under the overlay. Subtitle is the
                // raw 90+ count across the mock week.
                if (isScore90Paywall) {
                  const card = (
                    <PaywallOverlay
                      title="Signal exceptionnel · Réservé Pro"
                      subtitle={`${score90Count}\u00A0signaux 90+ détectés cette semaine`}
                    >
                      <SignalCard signal={s} index={i} />
                    </PaywallOverlay>
                  )
                  return (
                    <Fragment key={s.id}>
                      <h2 className="sr-only">
                        Signal {s.id} — {s.direction === "YES" ? "BUY YES" : "BUY NO"}
                      </h2>
                      {i === 0 ? <div id="first-signal-card">{card}</div> : card}
                    </Fragment>
                  )
                }

                // Daily limit gate: indexes 0-4 render normally, index 5
                // is replaced by a full-width upsell card, indexes 6+
                // render blurred under a minimal «Réservé Pro» overlay.
                if (isLimitHit && i === 5) {
                  return (
                    <motion.div
                      key={`upsell-${s.id}`}
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
                      className="xl:col-span-2 flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong bg-obsidian-850/40 p-8 text-center"
                    >
                      <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-brand-400">
                        Plan Free
                      </p>
                      <p className="mt-2 font-display text-body-lg font-medium text-ink">
                        Tu as vu tes 5&nbsp;signaux d’aujourd’hui
                      </p>
                      <p className="mt-1 text-body-md text-ink-muted max-w-md">
                        Pro débloque l’illimité
                      </p>
                      <button
                        type="button"
                        onClick={goToPricing}
                        className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-brand-500 px-5 py-2.5 text-body-md font-semibold text-obsidian-900 hover:bg-brand-400 transition-premium cursor-pointer"
                      >
                        Essai 7&nbsp;jours gratuit
                      </button>
                    </motion.div>
                  )
                }

                if (isLimitHit && i > 5) {
                  return (
                    <Fragment key={s.id}>
                      <h2 className="sr-only">
                        Signal {s.id} — {s.direction === "YES" ? "BUY YES" : "BUY NO"}
                      </h2>
                      <PaywallOverlay title="Réservé Pro">
                        <SignalCard signal={s} index={i} />
                      </PaywallOverlay>
                    </Fragment>
                  )
                }

                return (
                  <Fragment key={s.id}>
                    <h2 className="sr-only">
                      Signal {s.id} — {s.direction === "YES" ? "BUY YES" : "BUY NO"}
                    </h2>
                    {i === 0 ? (
                      <div id="first-signal-card">
                        <SignalCard signal={s} index={i} />
                      </div>
                    ) : (
                      <SignalCard signal={s} index={i} />
                    )}
                  </Fragment>
                )
              })}
            </AnimatePresence>
          </motion.div>
        )}
      </section>

      {/* First-visit coach-mark — points at the top card and explains the
          60-second pitch. Dismiss writes the seen flag so it never reappears. */}
      <CoachMark
        targetId="first-signal-card"
        open={coachOpen && filtered.length > 0}
        onDismiss={dismissCoach}
        message={"Ton premier signal est en haut — clique pour voir l\u2019analyse complète\u00A0: sources, sizing, fenêtre."}
      />

      {/* Mobile filters drawer */}
      <AnimatePresence>
        {filtersOpen && (
          <MobileFiltersDrawer
            onClose={() => setFiltersOpen(false)}
            category={category}
            setCategory={setCategory}
            minScore={minScore}
            setMinScore={setMinScore}
            direction={direction}
            setDirection={setDirection}
            onReset={resetFilters}
          />
        )}
      </AnimatePresence>
    </AppShell>
  )
}

function FilterPill({
  children,
  active,
  onClick,
  size = "md",
  tone,
}: {
  children: React.ReactNode
  active: boolean
  onClick: () => void
  size?: "sm" | "md"
  tone?: "yes" | "no"
}) {
  const toneActive =
    tone === "yes"
      ? "border-signal-yes/50 bg-signal-yes/10 text-signal-yes"
      : tone === "no"
        ? "border-signal-no/50 bg-signal-no/10 text-signal-no"
        : "border-line-strong bg-obsidian-700 text-ink shadow-inset-line"

  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1 rounded-full border transition-premium whitespace-nowrap cursor-pointer",
        size === "sm" ? "px-2.5 py-1 text-label-sm" : "px-3 py-1.5 text-body-sm",
        active
          ? toneActive
          : "border-line bg-obsidian-850/60 text-ink-muted hover:text-ink hover:border-line-strong",
      )}
    >
      {children}
    </button>
  )
}

function Divider() {
  return <span className="hidden lg:block h-4 w-px bg-line-strong" />
}

function EmptyState({ onReset }: { onReset: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mx-auto max-w-md rounded-2xl border border-dashed border-line-strong bg-obsidian-850/40 py-16 text-center"
    >
      <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-full bg-obsidian-800 text-ink-dim">
        <Filter className="h-6 w-6" />
      </div>
      <h3 className="mb-1 font-display text-lg text-ink">Aucun signal dans cette tranche</h3>
      <p className="mb-5 px-8 text-body-md text-ink-muted">
        Essaie d’élargir les filtres — le pipeline scanne en continu.
      </p>
      <button
        onClick={onReset}
        className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800 px-4 py-2 text-body-sm font-medium text-ink hover:border-brand-500/40 transition-premium cursor-pointer"
      >
        Réinitialiser les filtres
      </button>
    </motion.div>
  )
}

function MobileFiltersDrawer({
  onClose,
  category,
  setCategory,
  minScore,
  setMinScore,
  direction,
  setDirection,
  onReset,
}: {
  onClose: () => void
  category: CategoryKey
  setCategory: (k: CategoryKey) => void
  minScore: number
  setMinScore: (n: number) => void
  direction: DirectionKey
  setDirection: (k: DirectionKey) => void
  onReset: () => void
}) {
  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-40 bg-obsidian-950/80 backdrop-blur-sm"
      />
      <FocusLock returnFocus>
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby="mobile-filters-title"
        initial={{ y: "100%" }}
        animate={{ y: 0 }}
        exit={{ y: "100%" }}
        transition={{ type: "tween", duration: DURATIONS.default, ease: EASE_PREMIUM }}
        className="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl border-t border-line bg-obsidian-900 max-h-[85vh] overflow-y-auto"
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-line/60 bg-obsidian-900/95 backdrop-blur px-5 py-4">
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-brand-400" />
            <h3 id="mobile-filters-title" className="font-display text-base font-semibold text-ink">Filtres</h3>
          </div>
          <button onClick={onClose} aria-label="Fermer" className="grid h-9 w-9 place-items-center rounded-md text-ink-dim hover:text-ink hover:bg-obsidian-800 cursor-pointer">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-7 p-5 pb-8">
          <div>
            <p className="mb-2.5 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Catégorie</p>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((c) => (
                <FilterPill key={c.key} active={category === c.key} onClick={() => setCategory(c.key)}>
                  {c.label}
                </FilterPill>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2.5 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Catalyseur minimum</p>
            <div className="flex flex-wrap gap-1.5">
              {SCORE_STEPS.map((s) => (
                <FilterPill key={s.value} active={minScore === s.value} onClick={() => setMinScore(s.value)}>
                  {s.label}
                  {s.value === 90 && <PaywallChip />}
                </FilterPill>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-2.5 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">Direction</p>
            <div className="flex flex-wrap gap-1.5">
              <FilterPill active={direction === "all"} onClick={() => setDirection("all")}>
                Tous
              </FilterPill>
              <FilterPill active={direction === "YES"} onClick={() => setDirection("YES")} tone="yes">
                ▲ YES
              </FilterPill>
              <FilterPill active={direction === "NO"} onClick={() => setDirection("NO")} tone="no">
                ▼ NO
              </FilterPill>
            </div>
          </div>
        </div>

        <div className="sticky bottom-0 flex gap-2 border-t border-line/60 bg-obsidian-900/95 backdrop-blur p-4">
          <button
            onClick={onReset}
            className="flex-1 inline-flex items-center justify-center rounded-md border border-line-strong bg-obsidian-800 px-4 py-2.5 text-body-md font-medium text-ink cursor-pointer"
          >
            Réinitialiser
          </button>
          <button
            onClick={onClose}
            className="flex-[2] inline-flex items-center justify-center rounded-md bg-brand-500 px-4 py-2.5 text-body-md font-semibold text-obsidian-900 hover:bg-brand-400 transition-premium cursor-pointer"
          >
            Voir les résultats
          </button>
        </div>
      </motion.div>
      </FocusLock>
    </>
  )
}
