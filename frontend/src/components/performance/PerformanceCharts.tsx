/**
 * Recharts bundle for the Performance page.
 *
 * Recharts (~430 KB raw, ~120 KB gzipped) is the heaviest single
 * dependency on the page and is touched on **only one route** —
 * `/performance`. Pulling its imports into this lazy module means the
 * Performance page chunk downloads in two phases:
 *
 *   1. Page shell + KPIs + insights + Telegram card (immediate)
 *   2. Recharts bundle (this module) — downloaded in parallel with the
 *      page, rendered inside `<Suspense fallback={<ChartSkeleton/>}>`
 *
 * Above-the-fold content paints before recharts arrives, and users who
 * never scroll to the charts (or whose tab disconnects mid-load) avoid
 * the cost entirely.
 *
 * `THEME`, `DarkTooltip`, and `ChartCard` live here on purpose — they
 * are recharts-coupled and have no reason to exist in the eager
 * Performance.tsx bundle.
 */
import { motion } from "framer-motion"
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
import { DURATIONS, EASE_PREMIUM } from "@/lib/motion"
import { categoryWithEmoji } from "@/lib/utils"
import type { PerformanceStats } from "@/types/signal"
import type { ScoreVsMoveDataPoint } from "@/data/performance"

/* ───────────── Theme ───────────── */

// Chart palette. Values align with tailwind tokens: chart-brand, chart-yes,
// chart-no, chart-amber. Recharts / inline SVG consumers need raw hex, hence
// we mirror the token values here. `brandBright` maps to brand-300.
const THEME = {
  brand: "#0BE0A6",
  brandBright: "#5DFFCE",
  yes: "#4ADE80",
  no: "#F87171",
  amber: "#FBBF24",
  grid: "#1D2536",
  axis: "#5C6A82",
  tooltipBg: "#0B1220",
  tooltipBorder: "#1D2536",
}

const SCATTER_EMPTY_STATE_THRESHOLD = 30

/* ───────────── Local building blocks ───────────── */

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

/* ───────────── Public bundle ───────────── */

type Props = {
  stats: PerformanceStats
  gainsData: ReadonlyArray<{ week: string; gain: number; cumulative: number }>
  donutData: ReadonlyArray<{ name: string; value: number; color: string }>
  scoreVsMove: ReadonlyArray<ScoreVsMoveDataPoint>
  formatAxisDate: (iso: string) => string
  formatMoney: (amountUSD: number, opts?: { signed?: boolean; decimals?: number }) => string
  strongScoreWinRate: number
  scatterHasEnough: boolean
  resolvedCount: number
}

/**
 * Default export so the parent can `React.lazy(() => import("./PerformanceCharts"))`.
 * Keeps all four ChartCard tiles together so they share a single
 * Suspense boundary — first paint of the page header + KPIs is never
 * blocked on recharts.
 */
export default function PerformanceCharts({
  stats,
  gainsData,
  donutData,
  scoreVsMove,
  formatAxisDate,
  formatMoney,
  strongScoreWinRate,
  scatterHasEnough,
  resolvedCount,
}: Props) {
  return (
    <div className="grid gap-4 md:gap-5 xl:grid-cols-2">
      {/* Chart 1 — Win rate over time */}
      <ChartCard
        title="Taux de réussite dans le temps"
        subtitle={`Toi ${Math.round(stats.userWinRate * 100)}% · Plateforme ${Math.round(
          stats.platformWinRate * 100,
        )}%`}
      >
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={stats.winRateOverTime}
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
            data={[...gainsData]}
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
        subtitle={`Sur ${stats.userSignalsFollowed} signaux suivis`}
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
                  data={[...donutData]}
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
                (d.value / stats.userSignalsFollowed) * 100,
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
              data={[...scoreVsMove]}
              isAnimationActive={false}
            >
              {scoreVsMove.map((p, i) => (
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
  )
}
