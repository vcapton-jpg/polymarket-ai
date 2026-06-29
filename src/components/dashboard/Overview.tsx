import type { ComponentType, ReactNode } from 'react'
import { Inbox, Zap, Sparkles, Clock } from 'lucide-react'
import { AnimatedCounter } from '../ui/AnimatedCounter'
import { Reveal } from '../ui/Reveal'
import { KPIS, HOURLY_VOLUME, CHANNELS, CATEGORIES } from '../../demo/data'
import { VolumeChart, ChannelDonut, CategoryBars } from './charts'

/** Écran d'accueil du dashboard : KPIs animés + graphiques. */
export function Overview() {
  return (
    <div className="space-y-5">
      {/* Compteurs clés */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard icon={Inbox} tint="#7c5cff" label="Demandes traitées aujourd'hui" delay={0}>
          <AnimatedCounter value={KPIS.treatedToday} />
        </StatCard>
        <StatCard
          icon={Zap}
          tint="#34d399"
          label="Temps de réponse moyen"
          delay={0.06}
          sub={<span className="text-rose-400/70 line-through">{KPIS.manualResponse} en manuel</span>}
        >
          <AnimatedCounter value={KPIS.avgResponseSec} suffix=" s" />
        </StatCard>
        <StatCard icon={Sparkles} tint="#9a82ff" label="Taux d'automatisation" delay={0.12}>
          <AnimatedCounter value={KPIS.automationRate} suffix=" %" />
        </StatCard>
        <StatCard icon={Clock} tint="#fbbf24" label="Temps économisé cette semaine" delay={0.18}>
          <AnimatedCounter value={KPIS.hoursSavedWeek} suffix=" h" />
        </StatCard>
      </div>

      {/* Volume + canaux */}
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Volume entrant" subtitle="Aujourd'hui · par heure" delay={0.22} className="xl:col-span-2">
          <VolumeChart data={HOURLY_VOLUME} />
        </Card>
        <Card title="Par canal" subtitle="Tout fusionné en une vue" delay={0.28}>
          <ChannelDonut data={CHANNELS} />
        </Card>
      </div>

      {/* Catégories */}
      <Card title="Par catégorie" subtitle="Demandes triées automatiquement" delay={0.32}>
        <CategoryBars data={CATEGORIES} />
      </Card>
    </div>
  )
}

function StatCard({
  icon: Icon,
  tint,
  label,
  children,
  sub,
  delay = 0,
}: {
  icon: ComponentType<{ className?: string }>
  tint: string
  label: string
  children: ReactNode
  sub?: ReactNode
  delay?: number
}) {
  return (
    <Reveal delay={delay}>
      <div className="rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5 transition-colors hover:border-white/10">
        <div className="flex items-center gap-2.5">
          <span
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in srgb, ${tint} 14%, transparent)`, color: tint }}
          >
            <Icon className="h-4 w-4" />
          </span>
          <span className="text-xs text-faint">{label}</span>
        </div>
        <div className="mt-3 text-[2rem] font-semibold leading-none tracking-tight text-cloud tabular-nums">
          {children}
        </div>
        {sub && <div className="mt-2.5 text-xs">{sub}</div>}
      </div>
    </Reveal>
  )
}

function Card({
  title,
  subtitle,
  children,
  className = '',
  delay = 0,
}: {
  title: string
  subtitle?: string
  children: ReactNode
  className?: string
  delay?: number
}) {
  return (
    <Reveal delay={delay} className={className}>
      <div className="h-full rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5">
        <div className="mb-5 flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-cloud">{title}</h3>
          {subtitle && <span className="text-xs text-faint">{subtitle}</span>}
        </div>
        {children}
      </div>
    </Reveal>
  )
}
