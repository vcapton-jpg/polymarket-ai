import {
  BookOpen,
  Users,
  Sparkles,
  FileCheck,
  Target,
  Gauge,
  TrendingUp,
  MapPin,
  ShieldCheck,
  RotateCcw,
} from 'lucide-react'
import { Reveal } from '../ui/Reveal'

/** Comment Tempo s'adapte à l'activité spécifique d'UHM (presse jeunesse, abonnements). */
const ADAPT = [
  {
    icon: BookOpen,
    title: 'Vos 30+ titres',
    desc: 'Mickey Junior, Abricot, Quelle Histoire, Epsiloon… chaque magazine, ses numéros, son public, ses spécificités.',
  },
  {
    icon: Users,
    title: 'Vos 3 interlocuteurs',
    desc: 'L’enfant lecteur, mais surtout le parent et le grand-parent qui achètent — l’IA adapte le ton à chacun.',
  },
  {
    icon: Sparkles,
    title: 'Votre voix de marque',
    desc: 'Chaleureuse, proche des familles — apprise sur vos réponses passées, jamais un ton robotique générique.',
  },
  {
    icon: FileCheck,
    title: 'Vos politiques',
    desc: 'Abonnements, livraison, remboursements, RGPD jeunesse : vos règles deviennent celles de l’IA.',
  },
]

const STEPS = [
  {
    n: '01',
    icon: Target,
    when: 'Semaine 1',
    title: 'Pilote ciblé',
    desc: 'On branche Tempo sur UN canal et UNE catégorie, en parallèle de vos outils. Rien ne change dans votre système.',
    example: 'Ex. : les emails « je n’ai pas reçu mon numéro » — votre 1er motif en volume.',
  },
  {
    n: '02',
    icon: Gauge,
    when: 'Semaines 2-3',
    title: 'Mesure',
    desc: 'On mesure ensemble le temps gagné, la qualité des réponses et la satisfaction. Chaque réponse reste validable.',
    example: 'Vous gardez le contrôle total — l’IA ne décide jamais seule sur le sensible.',
  },
  {
    n: '03',
    icon: TrendingUp,
    when: 'Ensuite',
    title: 'Extension progressive',
    desc: 'Si les résultats sont là, on étend canal par canal, catégorie par catégorie, à votre rythme.',
    example: 'Jamais de bascule brutale : vous décidez de chaque palier.',
  },
]

const TRUST = [
  { icon: MapPin, label: 'Hébergé en Europe' },
  { icon: ShieldCheck, label: 'Conforme RGPD' },
  { icon: RotateCcw, label: 'Réversible à tout moment' },
]

/** Parcours d'intégration — adaptation au métier + pilote sans risque. */
export function Onboarding() {
  return (
    <div className="mx-auto max-w-5xl space-y-8 py-2">
      <Reveal>
        <div className="text-center">
          <h2 className="text-2xl font-semibold tracking-tight text-cloud">
            On commence petit, en parallèle, sans rien casser.
          </h2>
          <p className="mx-auto mt-2 max-w-xl text-sm text-mist">
            Tempo s’adapte d’abord à votre métier, puis se déploie par un pilote ciblé — vous gardez
            la main à chaque étape.
          </p>
        </div>
      </Reveal>

      {/* Adaptation au métier UHM */}
      <Reveal delay={0.05}>
        <div className="rounded-2xl border border-accent/15 bg-accent/[0.04] p-6">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-accent-200">
            <Sparkles className="h-4 w-4 text-accent" /> Tempo apprend VOTRE activité — pas un bot
            générique
          </div>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {ADAPT.map((a) => (
              <div key={a.title}>
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/12 text-accent ring-1 ring-accent/20">
                  <a.icon className="h-[18px] w-[18px]" />
                </span>
                <p className="mt-3 font-medium text-cloud">{a.title}</p>
                <p className="mt-1 text-sm leading-relaxed text-mist">{a.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </Reveal>

      {/* Timeline du pilote */}
      <div>
        <p className="mb-4 text-center text-[11px] font-semibold uppercase tracking-[0.16em] text-faint">
          Le pilote, sans risque, en 3 étapes
        </p>
        <div className="grid gap-4 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={0.1 + i * 0.08}>
              <div className="flex h-full flex-col rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5">
                <div className="flex items-center justify-between">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/12 text-accent ring-1 ring-accent/20">
                    <s.icon className="h-5 w-5" />
                  </span>
                  <span className="font-mono text-2xl font-semibold text-white/10">{s.n}</span>
                </div>
                <span className="mt-4 inline-block w-fit rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-medium text-faint">
                  {s.when}
                </span>
                <h3 className="mt-2 font-semibold text-cloud">{s.title}</h3>
                <p className="mt-1.5 flex-1 text-sm leading-relaxed text-mist">{s.desc}</p>
                <p className="mt-3 border-t border-white/[0.06] pt-3 text-xs leading-relaxed text-accent-200/80">
                  {s.example}
                </p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>

      {/* Réassurance */}
      <Reveal delay={0.3}>
        <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-3 rounded-2xl border border-white/[0.06] bg-ink-900/40 p-5">
          {TRUST.map((t) => (
            <span key={t.label} className="inline-flex items-center gap-2 text-sm text-mist">
              <t.icon className="h-4 w-4 text-accent" />
              {t.label}
            </span>
          ))}
        </div>
      </Reveal>
    </div>
  )
}
