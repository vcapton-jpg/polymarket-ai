import { lazy, Suspense, useMemo } from "react"
import { useTranslation } from "react-i18next"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import {
  Activity,
  AlertTriangle,
  Bell,
  CheckCircle2,
  Lightbulb,
  Send,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
} from "lucide-react"
import { Link } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { KPIStat } from "@/components/portfolio/KPIStat"
import { ChartSkeleton } from "@/components/ui/ChartSkeleton"
import {
  MOCK_PERSONAL_INSIGHTS,
  MOCK_SCORE_VS_MOVE,
  MOCK_WEEKLY_PNL,
} from "@/data/performance"
import { MOCK_RESOLVED_POSITIONS } from "@/data/positions"
import { useUserPreferences } from "@/lib/userPreferences"
import { usePerformance } from "@/hooks/usePerformance"
import { cn, categoryColor, categoryWithEmoji } from "@/lib/utils"
import type { PersonalInsight } from "@/data/performance"

/**
 * Recharts (~430 KB) is loaded only when this lazy chunk paints. The
 * page header, KPIs, category table, and Telegram card render
 * immediately — the four charts arrive in a second wave with a
 * ChartSkeleton fallback. See components/performance/PerformanceCharts.tsx.
 */
const PerformanceCharts = lazy(
  () => import("@/components/performance/PerformanceCharts"),
)

const SCATTER_EMPTY_STATE_THRESHOLD = 30

/* ───────────── Page ───────────── */

export default function Performance() {
  const { t } = useTranslation()
  const { formatMoney, language } = useUserPreferences()
  const { stats: MOCK_PERFORMANCE, loading: loadingCharts } = usePerformance()

  const dateLocale = language === "fr" ? "fr-FR" : "en-US"
  const formatAxisDate = (iso: string): string => {
    try {
      return new Date(iso).toLocaleDateString(dateLocale, {
        day: "2-digit",
        month: "short",
      })
    } catch {
      return iso
    }
  }

  const resolvedCount = MOCK_RESOLVED_POSITIONS.filter((p) => p.resolved).length

  // Derived: strong-score win rate (used in the scatter subtitle).
  const strongScoreWinRate = useMemo(() => {
    const strong = MOCK_SCORE_VS_MOVE.filter((p) => p.score > 75)
    if (!strong.length) return 0
    const correct = strong.filter((p) => p.correct).length
    return Math.round((correct / strong.length) * 100)
  }, [])

  // Derived: cumulative series for the gains bar chart.
  const gainsData = useMemo(() => {
    let cumulative = 0
    return MOCK_WEEKLY_PNL.map((p) => {
      cumulative += p.pnl
      return { week: p.week, gain: p.pnl, cumulative }
    })
  }, [])

  // Derived: donut distribution from the user's win rate categories.
  const donutData = useMemo(
    () =>
      MOCK_PERFORMANCE.userWinRateByCategory.map((c) => ({
        name: c.category,
        value: c.signalCount,
        color: categoryColor(c.category),
      })),
    [MOCK_PERFORMANCE.userWinRateByCategory],
  )

  const scatterHasEnough = resolvedCount >= SCATTER_EMPTY_STATE_THRESHOLD

  return (
    <AppShell
      breadcrumb={[{ label: t("performance.title") }]}
      liveCount={MOCK_PERFORMANCE.totalSignalsGenerated}
    >
      {/* Page header */}
      <div className="border-b border-line/60 bg-obsidian-900">
        <div className="px-4 pt-6 pb-5 md:px-8 md:pt-8">
          <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">
            {t("performance.eyebrow")}
          </p>
          <h1 className="font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2.125rem]">
            {t("performance.heading")}
          </h1>
          <p className="mt-1 text-[0.9375rem] text-ink-muted">
            {t("performance.subheading")}
          </p>
        </div>
      </div>

      <div className="px-4 py-6 md:px-8 md:py-8 space-y-10">
        {/* Section 1 — Personal KPIs */}
        <section>
          <SectionHeader
            eyebrow="Tes performances"
            title="Résumé"
            caption="Tes chiffres d’abord. Plus bas, les stats plateforme."
          />
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
            <KPIStat
              label="Signaux suivis"
              value={MOCK_PERFORMANCE.userSignalsFollowed}
              sub="Depuis inscription"
              icon={<Activity className="h-3.5 w-3.5" />}
            />
            <KPIStat
              label="Corrects"
              value={MOCK_PERFORMANCE.userCorrectPredictions}
              suffix={`/${MOCK_PERFORMANCE.userSignalsFollowed}`}
              tone="positive"
              sub={`${Math.round(MOCK_PERFORMANCE.userWinRate * 100)}% de réussite`}
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
            />
            <KPICategoryTile
              label="Meilleure catégorie"
              category={MOCK_PERFORMANCE.userBestCategory}
              winRate={MOCK_PERFORMANCE.userBestCategoryWinRate}
            />
            <KPIStat
              label="Gain estimé"
              value={MOCK_PERFORMANCE.userEstimatedGain}
              format={(n) => formatMoney(n, { signed: true })}
              tone={MOCK_PERFORMANCE.userEstimatedGain >= 0 ? "positive" : "negative"}
              sub="Cumulé sur positions résolues"
              icon={<TrendingUp className="h-3.5 w-3.5" />}
            />
          </div>
        </section>

        {/* Section 2 — Categories table */}
        <section>
          <SectionHeader
            eyebrow="Par catégorie"
            title="Tes performances par thème"
            caption="On affiche les mauvais chiffres aussi — pas de filtre flatteur."
          />
          <CategoryTable />
        </section>

        {/* Section 3 — Telegram card */}
        <section>
          <SectionHeader
            eyebrow="Canal Telegram"
            title="Tes alertes + ton comportement"
          />
          <TelegramCard />
        </section>

        {/* Section 4 — 4 charts */}
        <section>
          <SectionHeader
            eyebrow="Graphiques"
            title="Visualise ton évolution"
          />
          {!scatterHasEnough ? (
            <StatsEmptyState resolvedCount={resolvedCount} />
          ) : loadingCharts ? (
            <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
              {[0, 1, 2, 3].map((i) => (
                <ChartSkeleton key={i} />
              ))}
            </div>
          ) : (
            <Suspense
              fallback={
                <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
                  {[0, 1, 2, 3].map((i) => (
                    <ChartSkeleton key={i} />
                  ))}
                </div>
              }
            >
              <PerformanceCharts
                stats={MOCK_PERFORMANCE}
                gainsData={gainsData}
                donutData={donutData}
                scoreVsMove={MOCK_SCORE_VS_MOVE}
                formatAxisDate={formatAxisDate}
                formatMoney={formatMoney}
                strongScoreWinRate={strongScoreWinRate}
                scatterHasEnough={scatterHasEnough}
                resolvedCount={resolvedCount}
              />
            </Suspense>
          )}
        </section>

        {/* Section 5 — Personal insights */}
        <section>
          <SectionHeader
            eyebrow="Insights"
            title="Ce que tes données racontent"
          />
          <div className="grid gap-3 md:grid-cols-3">
            {MOCK_PERSONAL_INSIGHTS.map((insight, i) => (
              <InsightCard key={i} insight={insight} index={i} />
            ))}
          </div>
        </section>

        {/* Section 6 — Platform stats (discreet footer) */}
        <section>
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
            className="rounded-2xl border border-line/60 bg-obsidian-850/40 px-5 py-4 md:px-6 md:py-5"
          >
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 text-ink-dim" aria-hidden />
              <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
                Foresight en chiffres
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <PlatformStat
                label="Signaux générés"
                value={MOCK_PERFORMANCE.totalSignalsGenerated.toLocaleString(dateLocale)}
              />
              <PlatformStat
                label="Réussite globale"
                value={`${Math.round(MOCK_PERFORMANCE.platformWinRate * 100)}%`}
              />
              <PlatformStat
                label="Score moyen"
                value={MOCK_PERFORMANCE.platformAvgScore.toFixed(1)}
              />
              <PlatformStat
                label="Délai pipeline"
                value={`${MOCK_PERFORMANCE.avgPipelineDelay}s`}
              />
            </div>
          </motion.div>
        </section>
      </div>
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

function KPICategoryTile({
  label,
  category,
  winRate,
}: {
  label: string
  category: string
  winRate: number
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60 backdrop-blur-sm px-5 py-4"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-label-xs font-mono uppercase tracking-[0.14em] text-ink-dim">
          {label}
        </span>
        <Trophy className="h-3.5 w-3.5 text-ink-dim" aria-hidden />
      </div>
      <div className="font-display text-[1.5rem] font-semibold leading-none tracking-tight text-signal-yes">
        {categoryWithEmoji(category)}
      </div>
      <div className="mt-2 text-label-sm text-ink-muted">
        <span className="num text-ink">{Math.round(winRate * 100)}%</span> de réussite
      </div>
    </motion.div>
  )
}

function CategoryTable() {
  const { stats } = usePerformance()
  const sorted = useMemo(
    () =>
      [...stats.userWinRateByCategory].sort(
        (a, b) => b.winRate - a.winRate,
      ),
    [stats.userWinRateByCategory],
  )

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="overflow-hidden rounded-2xl border border-line-strong bg-obsidian-850/60"
    >
      <table className="w-full text-body-md">
        <thead className="border-b border-line/60 bg-obsidian-800/40">
          <tr className="text-left">
            <th scope="col" className="px-5 py-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
              Catégorie
            </th>
            <th scope="col" className="px-5 py-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim text-right">
              Signaux
            </th>
            <th scope="col" className="px-5 py-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim text-right">
              Taux
            </th>
            <th scope="col" className="px-5 py-3 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
              <span className="sr-only">Barre de progression</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line/60">
          {sorted.map((row) => {
            const pct = Math.round(row.winRate * 100)
            const color = categoryColor(row.category)
            const tone =
              row.winRate >= 0.7
                ? "text-signal-yes"
                : row.winRate >= 0.5
                  ? "text-ink"
                  : "text-signal-no"
            return (
              <tr key={row.category} className="transition-premium hover:bg-obsidian-800/30">
                <td className="px-5 py-3 text-ink">{categoryWithEmoji(row.category)}</td>
                <td className="num px-5 py-3 text-right text-ink-muted">{row.signalCount}</td>
                <td className={cn("num px-5 py-3 text-right font-semibold", tone)}>
                  {row.signalCount > 0 ? `${pct}%` : "—"}
                </td>
                <td className="px-5 py-3 w-[30%] min-w-[120px]">
                  <div className="h-1.5 rounded-full bg-obsidian-800 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${row.signalCount > 0 ? pct : 0}%` }}
                      transition={{ duration: 0.7, ease: EASE_PREMIUM }}
                      className="h-full rounded-full"
                      style={{ backgroundColor: color }}
                    />
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </motion.div>
  )
}

function TelegramCard() {
  const { stats } = usePerformance()
  const { telegramAlertsReceived, telegramAlertsFollowed, telegramFollowRate } = stats
  const pct = Math.round(telegramFollowRate * 100)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="relative overflow-hidden rounded-2xl border border-line-strong bg-gradient-to-br from-telegram/10 to-obsidian-850/60 px-5 py-5 md:px-6"
    >
      <div className="grid gap-5 md:grid-cols-[auto_1fr_auto] md:items-center">
        <div className="grid h-12 w-12 place-items-center rounded-xl border border-telegram/40 bg-telegram/10 text-telegram">
          <Send className="h-5 w-5" aria-hidden />
        </div>

        <div>
          <p className="mb-0.5 font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
            Tes alertes Telegram
          </p>
          <p className="font-display text-title-sm font-semibold text-ink md:text-title-md">
            <span className="num">{telegramAlertsReceived}</span> alertes reçues ·{" "}
            <span className="num">{telegramAlertsFollowed}</span> suivies
          </p>
          <p className="mt-1 text-body-sm text-ink-muted">
            Tu agis plus vite sur les signaux <span className="text-ink">Géopolitique</span>{" "}
            (75% suivis) que sur les signaux <span className="text-ink">Crypto</span> (20% suivis).
          </p>
        </div>

        <div className="flex flex-col items-start gap-1 md:items-end">
          <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
            Taux d’action
          </span>
          <span className="num font-display text-[1.75rem] font-semibold leading-none tracking-tight text-telegram">
            {pct}%
          </span>
          <div className="mt-1 h-1.5 w-28 overflow-hidden rounded-full bg-obsidian-800">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${pct}%` }}
              transition={{ duration: 0.8, ease: EASE_PREMIUM }}
              className="h-full rounded-full bg-telegram"
            />
          </div>
        </div>
      </div>
    </motion.div>
  )
}

function InsightCard({ insight, index }: { insight: PersonalInsight; index: number }) {
  const tone =
    insight.type === "positive"
      ? {
          border: "border-signal-yes/30",
          bg: "bg-signal-yes/5",
          iconBg: "bg-signal-yes/10",
          iconColor: "text-signal-yes",
        }
      : insight.type === "warning"
        ? {
            border: "border-signal-amber/30",
            bg: "bg-signal-amber/5",
            iconBg: "bg-signal-amber/10",
            iconColor: "text-signal-amber",
          }
        : {
            border: "border-brand-500/30",
            bg: "bg-brand-500/5",
            iconBg: "bg-brand-500/10",
            iconColor: "text-brand-300",
          }

  const Icon = insight.icon === "bulb" ? Lightbulb : AlertTriangle
  const fallbackIcon =
    insight.type === "positive" ? Target : insight.type === "warning" ? AlertTriangle : Bell
  const ResolvedIcon = insight.icon ? Icon : fallbackIcon

  return (
    <motion.article
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, delay: 0.05 * index, ease: EASE_PREMIUM }}
      className={cn(
        "rounded-2xl border px-4 py-4 md:px-5 md:py-5",
        tone.border,
        tone.bg,
      )}
    >
      <div className="mb-2 flex items-center gap-2">
        <span
          className={cn(
            "inline-flex h-7 w-7 items-center justify-center rounded-full",
            tone.iconBg,
            tone.iconColor,
          )}
          aria-hidden
        >
          <ResolvedIcon className="h-3.5 w-3.5" />
        </span>
      </div>
      <h3 className="mb-1 font-display text-[0.9375rem] font-semibold leading-snug text-ink">
        {insight.title}
      </h3>
      <p className="text-body-sm leading-relaxed text-ink-muted">{insight.body}</p>
    </motion.article>
  )
}

function StatsEmptyState({ resolvedCount }: { resolvedCount: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="rounded-2xl border border-dashed border-line-strong bg-obsidian-850/40 px-6 py-10 text-center"
    >
      <h3 className="font-display text-title-sm font-semibold text-ink md:text-title-md">
        Pas encore assez de données
      </h3>
      <p className="mx-auto mt-2 max-w-md text-body-md text-ink-muted">
        Il te faut {SCATTER_EMPTY_STATE_THRESHOLD} signaux résolus pour
        débloquer tes stats personnelles. Tu en as{" "}
        <span className="num text-ink">{resolvedCount}</span>.
      </p>
      <Link
        to="/signals"
        className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-brand-500 px-4 py-2 text-body-md font-semibold text-obsidian-900 hover:bg-brand-400 transition-premium"
      >
        Voir les signaux
      </Link>
    </motion.div>
  )
}

function PlatformStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="font-mono text-[0.625rem] uppercase tracking-[0.14em] text-ink-dim">
        {label}
      </p>
      <p className="num mt-1 font-display text-title-sm font-semibold tracking-tight text-ink">
        {value}
      </p>
    </div>
  )
}

