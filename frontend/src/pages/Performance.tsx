import { useMemo } from "react"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
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
import { MOCK_PERFORMANCE } from "@/data/performance"
import {
  MOCK_PERSONAL_INSIGHTS,
  MOCK_SCORE_VS_MOVE,
  MOCK_WEEKLY_PNL,
} from "@/data/performance"
import { MOCK_RESOLVED_POSITIONS } from "@/data/positions"
import { useUserPreferences } from "@/lib/userPreferences"
import { cn, categoryColor, categoryWithEmoji } from "@/lib/utils"
import type { PersonalInsight } from "@/data/performance"

/* ───────────── Chart theme ───────────── */

// Chart palette. Values align with tailwind tokens: chart-brand, chart-yes,
// chart-no, chart-amber. Recharts / inline SVG consumers need raw hex, hence
// we mirror the token values here. `brandBright` maps to brand-300.
const THEME = {
  brand: "#0BE0A6", // chart-brand / brand-500
  brandBright: "#5DFFCE", // brand-300
  yes: "#4ADE80", // chart-yes
  no: "#F87171", // chart-no
  amber: "#FBBF24", // chart-amber
  grid: "#1D2536",
  axis: "#5C6A82",
  tooltipBg: "#0B1220",
  tooltipBorder: "#1D2536",
}

const SCATTER_EMPTY_STATE_THRESHOLD = 30

/* ───────────── Page ───────────── */

export default function Performance() {
  const { formatMoney, language } = useUserPreferences()

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
    [],
  )

  const scatterHasEnough = resolvedCount >= SCATTER_EMPTY_STATE_THRESHOLD
  // Placeholder for when Performance data is fetched async. Flip to `true`
  // (e.g. during a SWR fetch) to preview the chart skeletons in-place.
  const loadingCharts = false

  return (
    <AppShell
      breadcrumb={[{ label: "Performance" }]}
      liveCount={MOCK_PERFORMANCE.totalSignalsGenerated}
    >
      {/* Page header */}
      <div className="border-b border-line/60 bg-obsidian-900">
        <div className="px-4 pt-6 pb-5 md:px-8 md:pt-8">
          <p className="mb-1 font-mono text-eyebrow uppercase text-brand-400">
            Performance
          </p>
          <h1 className="font-display text-[1.75rem] font-semibold tracking-tight text-ink md:text-[2.125rem]">
            Tes chiffres. Sans filtre.
          </h1>
          <p className="mt-1 text-[0.9375rem] text-ink-muted">
            Tout depuis ton inscription — y compris les catégories où tu perds.
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
          <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
            {/* Chart 1 — Win rate over time */}
            <ChartCard
              title="Taux de réussite dans le temps"
              subtitle={`Toi ${Math.round(MOCK_PERFORMANCE.userWinRate * 100)}% · Plateforme ${Math.round(
                MOCK_PERFORMANCE.platformWinRate * 100,
              )}%`}
            >
              <ResponsiveContainer width="100%" height={240}>
                <LineChart
                  data={MOCK_PERFORMANCE.winRateOverTime}
                  margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
                >
                  <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                    tickFormatter={formatAxisDate}
                  />
                  <YAxis
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                    tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
                    domain={[0.4, 0.9]}
                  />
                  <Tooltip
                    content={<DarkTooltip valueFormatter={(v) => `${Math.round(Number(v) * 100)}%`} />}
                  />
                  <Legend
                    verticalAlign="top"
                    height={24}
                    iconType="plainline"
                    wrapperStyle={{ fontSize: 11, color: THEME.axis, paddingBottom: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="user"
                    name="Toi"
                    stroke={THEME.brandBright}
                    strokeWidth={2.5}
                    dot={{ r: 3.5, fill: THEME.brandBright, strokeWidth: 0 }}
                    activeDot={{ r: 5 }}
                    isAnimationActive
                  />
                  <Line
                    type="monotone"
                    dataKey="platform"
                    name="Plateforme"
                    stroke={THEME.axis}
                    strokeWidth={1.5}
                    strokeDasharray="4 4"
                    dot={{ r: 2.5, fill: THEME.axis, strokeWidth: 0 }}
                    isAnimationActive
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Chart 2 — Weekly gains */}
            <ChartCard
              title="Tes gains par semaine"
              subtitle="Ligne en pointillé : cumul depuis 7 semaines"
            >
              <ResponsiveContainer width="100%" height={240}>
                <BarChart
                  data={gainsData}
                  margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
                >
                  <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="week"
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                  />
                  <YAxis
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                    tickFormatter={(v: number) => formatMoney(v)}
                    width={60}
                  />
                  <Tooltip
                    content={
                      <DarkTooltip
                        valueFormatter={(v, name) =>
                          name === "gain"
                            ? formatMoney(Number(v), { signed: true })
                            : formatMoney(Number(v), { signed: true })
                        }
                        labelFormatter={(label) => `Semaine ${label}`}
                      />
                    }
                  />
                  <ReferenceLine y={0} stroke={THEME.axis} strokeWidth={1} />
                  <Bar dataKey="gain" name="Gain" radius={[4, 4, 0, 0]}>
                    {gainsData.map((d, i) => (
                      <Cell key={i} fill={d.gain >= 0 ? THEME.yes : THEME.no} />
                    ))}
                  </Bar>
                  <Line
                    type="monotone"
                    dataKey="cumulative"
                    name="Cumul"
                    stroke={THEME.brandBright}
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={{ r: 2.5, fill: THEME.brandBright, strokeWidth: 0 }}
                    isAnimationActive
                  />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Chart 3 — Category donut */}
            <ChartCard
              title="Répartition de tes signaux"
              subtitle={`Sur ${MOCK_PERFORMANCE.userSignalsFollowed} signaux suivis`}
            >
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-5">
                <div className="sm:col-span-3">
                  <ResponsiveContainer width="100%" height={240}>
                    <PieChart>
                      <Tooltip
                        content={
                          <DarkTooltip
                            valueFormatter={(v) => `${v} signal${Number(v) > 1 ? "aux" : ""}`}
                          />
                        }
                      />
                      <Pie
                        data={donutData}
                        dataKey="value"
                        nameKey="name"
                        innerRadius={48}
                        outerRadius={86}
                        paddingAngle={2}
                        stroke="#0B1220"
                        strokeWidth={2}
                      >
                        {donutData.map((d, i) => (
                          <Cell key={i} fill={d.color} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <ul className="sm:col-span-2 flex flex-col justify-center gap-1.5 text-body-sm">
                  {donutData.map((d) => {
                    const pct = Math.round(
                      (d.value / MOCK_PERFORMANCE.userSignalsFollowed) * 100,
                    )
                    return (
                      <li key={d.name} className="flex items-center gap-2">
                        <span
                          className="h-2.5 w-2.5 shrink-0 rounded-full"
                          style={{ backgroundColor: d.color }}
                          aria-hidden
                        />
                        <span className="flex-1 truncate text-ink-muted">
                          {categoryWithEmoji(d.name)}
                        </span>
                        <span className="num font-mono text-label-xs text-ink">
                          {pct}%
                        </span>
                      </li>
                    )
                  })}
                </ul>
              </div>
            </ChartCard>

            {/* Chart 4 — Score vs move scatter */}
            <ChartCard
              title="Score du signal vs mouvement de marché"
              subtitle={`Tes signaux > 75 corrects dans ${strongScoreWinRate}% des cas`}
            >
              <ResponsiveContainer width="100%" height={240}>
                <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke={THEME.grid} strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="score"
                    name="Score"
                    domain={[50, 100]}
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                    label={{
                      value: "Score",
                      position: "insideBottom",
                      offset: -2,
                      fill: THEME.axis,
                      fontSize: 10,
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="marketMove"
                    name="Mouvement"
                    domain={[-15, 50]}
                    tick={{ fill: THEME.axis, fontSize: 11 }}
                    tickLine={false}
                    axisLine={{ stroke: THEME.grid }}
                    tickFormatter={(v: number) => `${v > 0 ? "+" : ""}${v}%`}
                    width={48}
                  />
                  <ReferenceLine y={0} stroke={THEME.axis} strokeWidth={1} />
                  <Tooltip
                    cursor={{ stroke: THEME.grid }}
                    content={
                      <DarkTooltip
                        valueFormatter={(v, name) => {
                          if (name === "Score") return String(v)
                          const n = Number(v)
                          return `${n > 0 ? "+" : ""}${n}%`
                        }}
                      />
                    }
                  />
                  <Scatter
                    name="Signaux"
                    data={MOCK_SCORE_VS_MOVE}
                    isAnimationActive={false}
                  >
                    {MOCK_SCORE_VS_MOVE.map((p, i) => (
                      <Cell key={i} fill={p.correct ? THEME.yes : THEME.no} />
                    ))}
                  </Scatter>
                </ScatterChart>
              </ResponsiveContainer>
              {!scatterHasEnough && (
                <p className="mt-3 text-label-sm leading-relaxed text-ink-dim">
                  Plus fiable à partir de {SCATTER_EMPTY_STATE_THRESHOLD} positions
                  résolues (tu en as <span className="num text-ink-muted">{resolvedCount}</span>). Les
                  tendances se stabilisent avec le temps.
                </p>
              )}
            </ChartCard>
          </div>
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
  const sorted = useMemo(
    () =>
      [...MOCK_PERFORMANCE.userWinRateByCategory].sort(
        (a, b) => b.winRate - a.winRate,
      ),
    [],
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
  const { telegramAlertsReceived, telegramAlertsFollowed, telegramFollowRate } = MOCK_PERFORMANCE
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

function ChartCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: string
  children: React.ReactNode
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.default, ease: EASE_PREMIUM }}
      className="rounded-2xl border border-line-strong bg-obsidian-850/60 px-4 py-4 md:px-5 md:py-5"
    >
      <div className="mb-3">
        <h3 className="font-display text-[0.9375rem] font-semibold text-ink">{title}</h3>
        {subtitle && (
          <p className="mt-0.5 text-label-sm text-ink-muted">{subtitle}</p>
        )}
      </div>
      {children}
    </motion.div>
  )
}

function DarkTooltip({
  active,
  payload,
  label,
  valueFormatter,
  labelFormatter,
}: {
  active?: boolean
  payload?: ReadonlyArray<{ name?: string; value?: number | string; color?: string }>
  label?: string | number
  valueFormatter?: (value: number | string, name?: string) => string
  labelFormatter?: (label: string | number) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line bg-obsidian-950/95 px-3 py-2 text-label-sm shadow-xl backdrop-blur-sm">
      {label !== undefined && (
        <p className="mb-1 font-mono text-[0.625rem] uppercase tracking-[0.14em] text-ink-dim">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      )}
      <ul className="space-y-0.5">
        {payload.map((p, i) => (
          <li key={i} className="flex items-center gap-2">
            {p.color && (
              <span
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: p.color }}
                aria-hidden
              />
            )}
            {p.name && <span className="text-ink-muted">{p.name}</span>}
            <span className="num ml-auto font-medium text-ink">
              {valueFormatter && p.value !== undefined
                ? valueFormatter(p.value, p.name)
                : p.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
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

