import type { ComponentType, ReactNode } from 'react'
import { Clock, Users, Sparkles, Zap, Calculator } from 'lucide-react'
import { AnimatedCounter } from '../ui/AnimatedCounter'
import { Reveal } from '../ui/Reveal'
import { VolumeChart, CategoryBars } from './charts'

const WEEKLY = [
  { h: 'Lun', v: 980 },
  { h: 'Mar', v: 1120 },
  { h: 'Mer', v: 1340 },
  { h: 'Jeu', v: 1247 },
  { h: 'Ven', v: 1410 },
  { h: 'Sam', v: 760 },
  { h: 'Dim', v: 540 },
]

const AUTOMATION_BY_CAT = [
  { label: 'Produit / éditorial', value: 88, color: '#60a5fa' },
  { label: 'Livraison', value: 84, color: '#7c5cff' },
  { label: 'Abonnement', value: 71, color: '#9a82ff' },
  { label: 'Facturation', value: 62, color: '#34d399' },
  { label: 'Réclamation', value: 23, color: '#fb7185' },
]

// Hypothèses affichées, pour que le chiffre € ne sorte pas de nulle part.
const HOURS_PER_WEEK = 142
const WEEKS = 4.33
const HOURLY = 30 // coût agent chargé (€/h)
const HOURS_MONTH = Math.round(HOURS_PER_WEEK * WEEKS)
const EURO_MONTH = HOURS_MONTH * HOURLY

const fmt = (n: number) => n.toLocaleString('fr-FR')

/** Analytics — performance, automatisation et gain estimé (transparent). */
export function Analytics() {
  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat icon={Clock} tint="#7c5cff" label="Temps de traitement économisé / sem." delay={0}>
          <AnimatedCounter value={HOURS_PER_WEEK} suffix=" h" />
        </Stat>
        <Stat icon={Users} tint="#34d399" label="Équivalent redéployé" delay={0.06} sub={<span className="text-faint">sur les demandes à valeur</span>}>
          <span>≈ <AnimatedCounter value={3.6} decimals={1} /> ETP</span>
        </Stat>
        <Stat icon={Sparkles} tint="#9a82ff" label="Taux d'automatisation" delay={0.12}>
          <AnimatedCounter value={73} suffix=" %" />
        </Stat>
        <Stat icon={Zap} tint="#fbbf24" label="Temps de réponse moyen" delay={0.18} sub={<span className="text-rose-400/70 line-through">4 h 30 en manuel</span>}>
          <AnimatedCounter value={8} suffix=" s" />
        </Stat>
      </div>

      {/* Gain € — transparent, sans boîte noire */}
      <Reveal delay={0.22}>
        <div className="rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5">
          <div className="mb-4 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-faint">
            <Calculator className="h-3.5 w-3.5 text-accent" /> Gain estimé — le calcul, sans boîte noire
          </div>
          <div className="space-y-2.5 font-mono text-[13px]">
            <CalcLine terms={[`${HOURS_PER_WEEK} h/sem.`, `${WEEKS} sem./mois`]} result={`${fmt(HOURS_MONTH)} h/mois`} />
            <CalcLine terms={[`${fmt(HOURS_MONTH)} h/mois`, `${HOURLY} €/h (coût agent chargé)`]} result={`≈ ${fmt(EURO_MONTH)} €/mois`} highlight />
          </div>
          <p className="mt-4 text-[11px] leading-relaxed text-faint">
            Hypothèse prudente : coût agent chargé {HOURLY} €/h, temps économisé mesuré sur le mois en
            cours. On recalcule sur vos chiffres réels (volume, coûts internes) lors du pilote.
          </p>
        </div>
      </Reveal>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Volume traité" subtitle="7 derniers jours" delay={0.26}>
          <VolumeChart data={WEEKLY} />
        </Card>
        <Card title="Automatisation par catégorie" subtitle="Part traitée sans humain" delay={0.3}>
          <CategoryBars data={AUTOMATION_BY_CAT} />
        </Card>
      </div>
    </div>
  )
}

function CalcLine({ terms, result, highlight }: { terms: string[]; result: string; highlight?: boolean }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
      {terms.map((t, i) => (
        <span key={t} className="flex items-center gap-2.5">
          {i > 0 && <span className="text-faint">×</span>}
          <span className="text-mist">{t}</span>
        </span>
      ))}
      <span className="text-faint">=</span>
      <span className={highlight ? 'rounded-md bg-accent/15 px-2 py-0.5 font-semibold text-accent-300' : 'font-semibold text-cloud'}>
        {result}
      </span>
    </div>
  )
}

function Stat({
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
      <div className="rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ backgroundColor: `color-mix(in srgb, ${tint} 14%, transparent)`, color: tint }}>
            <Icon className="h-4 w-4" />
          </span>
          <span className="text-xs text-faint">{label}</span>
        </div>
        <div className="mt-3 text-[2rem] font-semibold leading-none tracking-tight text-cloud tabular-nums">{children}</div>
        {sub && <div className="mt-2.5 text-xs">{sub}</div>}
      </div>
    </Reveal>
  )
}

function Card({ title, subtitle, children, delay = 0 }: { title: string; subtitle?: string; children: ReactNode; delay?: number }) {
  return (
    <Reveal delay={delay}>
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
