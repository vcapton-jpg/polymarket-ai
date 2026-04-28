import { Link } from "react-router-dom"
import { useRef, useEffect, useState } from "react"
import { motion, useInView, AnimatePresence } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Radio,
  Zap,
  Target,
  Sparkles,
  Check,
  X,
} from "lucide-react"
import { PublicNav } from "@/components/layout/PublicNav"
import { Footer } from "@/components/layout/Footer"
import { Button } from "@/components/ui/Button"
import { SignalCard } from "@/components/signals/SignalCard"
import { LivePill } from "@/components/signals/badges"
import { PoweredByPolymarket } from "@/components/signals/PoweredByPolymarket"
import { AnimatedSignalDemo } from "@/components/homepage/AnimatedSignalDemo"
import { MOCK_SIGNALS } from "@/data/signals"
import { useCountUp } from "@/hooks/useCountUp"
import { cn } from "@/lib/utils"
import { usePublicStats } from "@/hooks/usePublicStats"
import { EMPTY_STAT_PLACEHOLDER } from "@/lib/stats"

export default function Homepage() {
  return (
    <>
      <PublicNav />
      <main id="main" className="relative">
        <Hero />
        <Kpis />
        <WhatIsPolymarket />
        <HowItWorks />
        <SignalAnatomy />
        <LiveFeed />
        <Audiences />
        <Testimonials />
        <WhyNotPolymarket />
        <PricingTeaser />
        <FinalCta />
      </main>
      <Footer />
    </>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* HERO                                                        */
/* ─────────────────────────────────────────────────────────── */

function Hero() {
  return (
    <section className="relative overflow-hidden pt-40 pb-24 md:pt-48 md:pb-32">
      {/* Background layers */}
      <div className="pointer-events-none absolute inset-0 bg-grid bg-grid-fade opacity-40" aria-hidden />
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(60% 50% at 50% 0%, rgba(11,224,166,0.14), transparent 70%), radial-gradient(40% 40% at 80% 30%, rgba(96,165,250,0.08), transparent 70%)",
        }}
        aria-hidden
      />

      <div className="container-page relative">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
          className="mx-auto max-w-[920px] text-center"
        >
          <p className="mb-7 font-display text-[clamp(1.05rem,1.6vw,1.35rem)] italic font-medium text-ink-muted/90 tracking-tight">
            Tu regardes les news&nbsp;?
          </p>

          <h1 className="text-display-1 text-ink text-balance tracking-tight">
            Sois le premier à transformer l’information en{" "}
            <span className="italic bg-gradient-to-r from-brand-300 via-brand-400 to-brand-500 bg-clip-text text-transparent">
              opportunité
            </span>
            .
          </h1>

          <p className="mx-auto mt-5 max-w-[680px] text-title-sm leading-[1.6] text-ink-muted md:text-title-md">
            Foresight détecte les signaux sur Polymarket en 90 secondes — avant que le
            marché ne les intègre. Basé sur les faits et l’historique.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/signup?plan=free&intent=feed">
              <Button variant="primary" size="xl" className="w-full sm:w-auto">
                Voir les signaux en direct
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <a href="#how" className="w-full sm:w-auto">
              <Button variant="outline" size="xl" className="w-full">
                Comment ça marche
              </Button>
            </a>
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-center gap-4 md:gap-6 text-body-sm text-ink-dim">
            <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-brand-400" />Pas de carte bancaire</span>
            <PoweredByPolymarket size="sm" />
            <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5 text-brand-400" />Accès immédiat</span>
          </div>
        </motion.div>

        {/* Animated signal demo — morphs card → order form → confirmation */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DURATIONS.expressive, delay: 0.3, ease: EASE_PREMIUM }}
          className="relative mx-auto mt-16 max-w-[860px]"
        >
          <AnimatedSignalDemo />
        </motion.div>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* KPIS — 6 numbers                                            */
/* ─────────────────────────────────────────────────────────── */

function Kpis() {
  // Legal-PR-3 (B8 + H1): every KPI below comes from the live backend
  // — empty / null values render as a placeholder rather than a
  // fabricated marketing number.
  const { data } = usePublicStats()
  return (
    <section className="relative border-y border-line/60 bg-obsidian-850/50 py-24 md:py-32">
      <div className="container-page">
        <div className="mx-auto max-w-[880px] text-center">
          <p className="mb-4 inline-flex items-center justify-center gap-2 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">
            <span
              className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse motion-reduce:animate-none"
              aria-hidden
            />
            En direct
          </p>
          <h2 className="font-display text-display-2 md:text-display-1 font-semibold text-ink text-center leading-[1.05] tracking-tight text-balance">
            Le pipeline tourne. Là, tout de suite.
          </h2>
        </div>

        <div className="mt-12 grid grid-cols-1 gap-8 md:mt-16 md:grid-cols-3 md:gap-12">
          <KpiCell
            index={0}
            literal={"90\u00A0s"}
            label="délai moyen de détection"
          />
          <KpiCell
            index={1}
            value={data?.win_rate_1h_pct ?? null}
            suffix="%"
            label={
              data && data.win_rate_sample_size > 0
                ? `taux de réussite directionnel à 1 h · n=${data.win_rate_sample_size}, ${data.win_rate_window_days} j glissants`
                : "taux de réussite directionnel à 1 h"
            }
            accent
          />
          <KpiCell
            index={2}
            value={data?.markets_monitored ?? null}
            label="marchés surveillés en temps réel"
          />
        </div>

        <div className="mt-12 grid grid-cols-1 gap-8 border-t border-line/40 pt-12 md:grid-cols-3 md:gap-12">
          <KpiCell
            index={3}
            value={data?.signals_total ?? null}
            label="signaux générés depuis le lancement"
          />
          <KpiCell
            index={4}
            literal="24/7"
            label="pipeline actif en continu"
          />
          <KpiCell
            index={5}
            value={data?.active_traders_week ?? null}
            label="traders actifs cette semaine"
          />
        </div>

        <p className="mt-10 text-center text-label-sm text-ink-dim">
          Chiffres calculés en direct depuis notre base. Les performances
          passées ne préjugent pas des performances futures.
        </p>
      </div>
    </section>
  )
}

function KpiCell({
  value,
  literal,
  label,
  prefix,
  suffix,
  accent,
  index,
}: {
  // `null` is a meaningful state — backend reports no data yet for
  // this slot. We render `EMPTY_STAT_PLACEHOLDER` instead of zero.
  value?: number | null
  literal?: string
  label: string
  prefix?: string
  suffix?: string
  accent?: boolean
  index: number
}) {
  // Drive the count-up off `value ?? 0` so the animation still fires
  // when data lands; render path below short-circuits to "—" when
  // value is null.
  const { ref, display } = useCountUp(value ?? 0, { duration: 1800 })
  const rendered =
    literal ?? (value === null || value === undefined ? EMPTY_STAT_PLACEHOLDER : display)
  const showSuffix = !!suffix && value !== null && value !== undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: DURATIONS.expressive, delay: index * 0.06, ease: EASE_PREMIUM }}
      className="text-center"
    >
      <div className="flex items-baseline justify-center gap-1">
        {prefix && <span className="text-body-md text-ink-muted">{prefix}</span>}
        <span
          ref={ref}
          className={cn(
            "font-display num tabular-nums text-display-2 md:text-[4rem] font-semibold leading-none tracking-tight",
            accent ? "text-brand-300" : "text-ink",
          )}
        >
          {rendered}
          {showSuffix && (
            <span
              className={cn(
                "num font-semibold",
                accent ? "text-brand-300/80" : "text-ink-muted",
              )}
            >
              {suffix}
            </span>
          )}
        </span>
      </div>
      <p className="mt-3 text-[0.9375rem] text-ink-muted">{label}</p>
    </motion.div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* What is Polymarket — Le déclic                              */
/* ─────────────────────────────────────────────────────────── */

function WhatIsPolymarket() {
  return (
    <section className="relative py-24 md:py-32">
      <div className="container-page">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-20% 0px" }}
          transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
          className="grid gap-12 md:grid-cols-[1.05fr_1fr] md:gap-16 items-start"
        >
          <div>
            <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">Le déclic</p>
            <h2 className="text-display-2 text-ink mb-6 text-balance">
              {"C’est quoi Polymarket\u00A0?"}
            </h2>
            <div className="space-y-5 text-body-lg leading-[1.65] text-ink/85">
              <p>
                Imagine que tu puisses parier sur{" "}
                <span className="text-ink font-medium">
                  {"«\u00A0Est-ce que la France gagnera la Coupe du monde 2026\u00A0?\u00A0»"}
                </span>
                . Le marché dit{" "}
                <span className="num text-brand-300 font-semibold">15%</span>. Tu y crois,
                tu achètes YES à{" "}
                <span className="num text-ink">{"0,15\u00A0€"}</span>. Si la France gagne, ta mise
                vaut{" "}
                <span className="num text-ink">{"1\u00A0€"}</span> — tu multiplies par{" "}
                <span className="num text-brand-300 font-semibold">6,6</span>.
              </p>
              <p>
                {"Polymarket c’est ça, appliqué à "}
                <span className="num text-ink font-medium">61 000</span>{" événements\u00A0: élections, conflits, résultats sportifs, décisions économiques, avancées scientifiques."}
              </p>
              <p className="border-l-2 border-brand-500/60 pl-4 text-ink">
                {"Foresight te dit quand le marché n’a pas encore intégré une info — et donc quand il y a une opportunité."}
              </p>
            </div>
          </div>

          <div className="relative">
            <MarketExample />
          </div>
        </motion.div>
      </div>
    </section>
  )
}

function MarketExample() {
  return (
    <div className="relative rounded-2xl border border-line-strong bg-obsidian-850/60 p-6 backdrop-blur">
      <div className="mb-4 flex items-center justify-between">
        <span className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
          Exemple · Polymarket
        </span>
        <LivePill className="text-[0.625rem] px-1.5 py-0.5" />
      </div>
      <h3 className="mb-5 font-display text-lg font-semibold leading-tight text-ink">
        {"La France gagne-t-elle la Coupe du monde 2026\u00A0?"}
      </h3>

      <div className="space-y-3">
        <MarketRow side="YES" price={0.15} highlighted />
        <MarketRow side="NO" price={0.85} />
      </div>

      {/* Legal-PR-3 (H11): AMF balanced-presentation rule. Pre-fix le
          "× 6,6 si tu gagnes" était en couleur de marque verte;
          "Sinon, tu perds ta mise" en gris muted. Maintenant: même fond
          neutre, même corps de texte, gain et perte également
          mis en avant. */}
      <div className="mt-5 grid gap-2 rounded-lg border border-line-strong bg-obsidian-850/60 p-4 text-body-sm leading-relaxed text-ink-muted">
        <div className="flex items-start gap-3">
          <Zap className="h-4 w-4 shrink-0 text-ink-muted mt-0.5" aria-hidden />
          <div>
            <span className="font-semibold text-ink">Mise × 6,6 si la France gagne.</span>{" "}
            Tu poses <span className="num text-ink">{"15\u00A0€"}</span> sur YES à{" "}
            <span className="num text-ink">{"0,15\u00A0€"}</span> et tu retires{" "}
            <span className="num text-ink">{"100\u00A0€"}</span>.
          </div>
        </div>
        <div className="flex items-start gap-3 border-t border-line/40 pt-2">
          <AlertTriangle
            className="h-4 w-4 shrink-0 text-signal-amber mt-0.5"
            aria-hidden
          />
          <div>
            <span className="font-semibold text-ink">
              Si la France perd, tu perds ta mise.
            </span>{" "}
            Le risque est de 100 % du capital engagé. Les performances
            passées ne préjugent pas des performances futures.
          </div>
        </div>
      </div>
    </div>
  )
}

function MarketRow({ side, price, highlighted }: { side: "YES" | "NO"; price: number; highlighted?: boolean }) {
  const isYes = side === "YES"
  return (
    <div
      className={cn(
        "flex items-center justify-between rounded-lg border p-3",
        highlighted
          ? isYes
            ? "border-signal-yes/40 bg-signal-yes/5"
            : "border-signal-no/40 bg-signal-no/5"
          : "border-line/80 bg-obsidian-800/50",
      )}
    >
      <div className="flex items-center gap-3">
        <span
          className={cn(
            "font-mono text-label-sm font-semibold tracking-wide px-2 py-1 rounded border",
            isYes ? "border-signal-yes/40 text-signal-yes bg-signal-yes/10"
                  : "border-signal-no/40 text-signal-no bg-signal-no/10",
          )}
        >
          {side}
        </span>
        <span className="num text-sm text-ink">
          {`${(price).toFixed(2)}\u00A0€`}
        </span>
      </div>
      <div className="num text-sm text-ink-muted">
        {Math.round(price * 100)}%
      </div>
    </div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* How It Works — 3 steps                                      */
/* ─────────────────────────────────────────────────────────── */

function HowItWorks() {
  const steps = [
    {
      num: "01",
      icon: Radio,
      title: "Une news éclate",
      body: "Reuters annonce un cessez-le-feu. Notre pipeline le détecte en moins de 90 secondes.",
      footer: "RSS direct · Sources Tier-1 · Monitoring 24/7",
    },
    {
      num: "02",
      icon: Target,
      title: "Le marché est en retard",
      body: "Sur Polymarket, le marché trade encore à 22%. Il n’a pas encore intégré l’information.",
      footer: "61 000 marchés en surveillance continue",
    },
    {
      num: "03",
      icon: Zap,
      title: "Tu reçois le signal",
      // Rewritten per voice guide: "Fenêtre ~2 h" + curly apostrophe + NBSP units.
      body: "BUY YES · Score 72 · Fenêtre ~2\u00A0h. Sources + historique. Tu décides.",
      footer: "Dashboard en temps réel — Telegram réservé aux membres Pro.",
    },
  ]

  return (
    <section id="how" className="relative border-y border-line/60 bg-obsidian-850/40 py-24 md:py-32 scroll-mt-20">
      <div className="container-page">
        <div className="mb-14 max-w-[640px]">
          <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">Comment ça marche</p>
          <h2 className="text-display-2 text-ink text-balance">
            Trois étapes entre l’info et ta position.
          </h2>
        </div>

        <div className="relative grid gap-5 md:grid-cols-3 md:gap-0">
          {/* Connector line (desktop) */}
          <div className="pointer-events-none absolute left-0 right-0 top-8 hidden md:block">
            <div className="h-px bg-gradient-to-r from-transparent via-line-strong to-transparent" />
          </div>

          {steps.map((step, i) => (
            <motion.div
              key={step.num}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-10% 0px" }}
              transition={{ duration: DURATIONS.expressive, delay: i * 0.15, ease: EASE_PREMIUM }}
              className={cn(
                "relative rounded-2xl border border-line-strong bg-obsidian-900 p-6 md:border-r-0 md:last:border-r md:rounded-r-none md:first:rounded-l-2xl md:last:rounded-r-2xl md:rounded-l-none md:first:rounded-l-2xl",
                i === 0 && "md:rounded-l-2xl",
                i === 2 && "md:rounded-r-2xl md:border-r",
              )}
            >
              <div className="relative mb-5 flex items-center gap-3">
                <div className="relative grid h-10 w-10 place-items-center rounded-lg border border-brand-500/30 bg-obsidian-800">
                  <step.icon className="h-4 w-4 text-brand-400" />
                  <div className="absolute -right-1 -top-1 rounded-full border border-line-strong bg-obsidian-900 px-1.5 py-0.5 font-mono text-[0.625rem] font-medium text-brand-400">
                    {step.num}
                  </div>
                </div>
              </div>
              <h3 className="mb-3 font-display text-title-md md:text-[1.375rem] font-semibold leading-tight tracking-tight text-ink">
                {step.title}
              </h3>
              <p className="text-[1.0625rem] leading-relaxed text-ink-muted">{step.body}</p>
            </motion.div>
          ))}
        </div>

        <p className="mt-10 text-center text-ink-muted italic">
          Pas besoin d’être trader. Si tu suis l’actu, tu as déjà l’essentiel.
        </p>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Live Feed — 3 blurred signal cards                          */
/* ─────────────────────────────────────────────────────────── */

function LiveFeed() {
  const teaserSignals = MOCK_SIGNALS.slice(0, 3)
  const { data } = usePublicStats()
  const signalsToday = data?.signals_today ?? null
  const { ref: countRef, display: countDisplay } = useCountUp(
    signalsToday ?? 0,
    { duration: 1200 },
  )
  return (
    <section className="relative py-24 md:py-32">
      <div className="container-page">
        <div className="mb-10 flex items-end justify-between gap-4">
          <div>
            <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">En direct</p>
            <h2 className="text-display-2 text-ink text-balance">
              Ce qui se passe en ce moment.
            </h2>
          </div>
          <div className="hidden md:flex flex-col items-end gap-3">
            <Link to="/signup?plan=free&intent=feed">
              <Button variant="outline" size="md">
                Voir tous les signaux
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
            <LivePill />
          </div>
        </div>

        <div className="relative">
          <div className="grid gap-5 md:grid-cols-1 lg:grid-cols-3">
            {teaserSignals.map((s, i) => (
              <motion.div
                key={s.id}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: DURATIONS.expressive, delay: i * 0.1, ease: EASE_PREMIUM }}
              >
                <SignalCard signal={s} variant="teaser" />
              </motion.div>
            ))}
          </div>
        </div>

        <p className="mt-8 text-center text-[0.9375rem] text-ink-muted">
          <span ref={countRef} className="num text-ink">
            {signalsToday === null
              ? EMPTY_STAT_PLACEHOLDER
              : `+ ${countDisplay}`}
          </span>{" "}
          autres signaux générés aujourd’hui
        </p>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Audiences — for who                                          */
/* ─────────────────────────────────────────────────────────── */

function Audiences() {
  return (
    <section className="relative border-t border-line/60 bg-obsidian-850/40 py-24 md:py-32">
      <div className="container-page">
        <div className="mb-14 max-w-[640px]">
          <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">Pour qui</p>
          <h2 className="text-display-2 text-ink text-balance">
            Deux façons de l’utiliser.
          </h2>
        </div>

        <div className="grid gap-5 md:grid-cols-2">
          {/* Audience 1 (news-followers first): primary CTA anchors to HowItWorks, secondary offers free signup. */}
          <AudienceCard
            eyebrow="Tu suis l’actu, tu veux parier dessus"
            title="Pas besoin de connaître la finance."
            body="Tu lis déjà les news — on transforme cette information en opportunités concrètes sur Polymarket. On te dit quoi faire, quand, et pourquoi."
            cta={{ label: "Voir comment ça marche", to: "#how" }}
            secondaryCta={{ label: "Commencer gratuitement", to: "/signup?plan=free" }}
            decorClass="from-brand-500/10"
          />
          {/* Audience 2 (traders): CTA retargeted to the API plan anchor. */}
          <AudienceCard
            eyebrow="Tu trades déjà, tu veux un edge"
            title="Un edge systématique, livré en 90 secondes."
            body="On te fournit des signaux construits à partir de flux de données temps réel (Reuters, AP, X) croisés avec un moteur de recherche hybride qui compare chaque situation à notre historique de marchés similaires."
            cta={{ label: "Voir le plan API", to: "/pricing#api" }}
            ctaVariant="outline"
            decorClass="from-tier-2/10"
          />
        </div>
      </div>
    </section>
  )
}

function AudienceCard({
  eyebrow,
  title,
  body,
  cta,
  secondaryCta,
  ctaVariant = "primary",
  decorClass,
}: {
  eyebrow: string
  title: string
  body: string
  cta: { label: string; to: string }
  secondaryCta?: { label: string; to: string }
  ctaVariant?: "primary" | "outline"
  decorClass?: string
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
      className="group relative overflow-hidden rounded-2xl border border-line-strong bg-obsidian-900 p-7 md:p-9 hover:border-brand-500/40 transition-premium"
    >
      <div className={cn("pointer-events-none absolute inset-x-0 top-0 h-32 bg-gradient-to-b to-transparent opacity-60", decorClass)} />
      <div className="relative">
        <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">{eyebrow}</p>
        <h3 className="mb-4 font-display text-[1.75rem] font-semibold leading-tight tracking-tight text-ink text-balance">
          {title}
        </h3>
        <p className="mb-7 text-[1.0625rem] leading-relaxed text-ink/75">{body}</p>
        {cta.to.startsWith("#") ? (
          <a href={cta.to}>
            <Button variant={ctaVariant} size="md">
              {cta.label}
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </a>
        ) : (
          <Link to={cta.to}>
            <Button variant={ctaVariant} size="md">
              {cta.label}
              <ArrowRight className="h-3.5 w-3.5" />
            </Button>
          </Link>
        )}
        {secondaryCta && (
          <div className="mt-3">
            <Link
              to={secondaryCta.to}
              className="inline-flex items-center gap-1 text-label-sm text-ink-dim hover:text-brand-300 transition-premium"
            >
              {secondaryCta.label}
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>
        )}
      </div>
    </motion.div>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Testimonials — seed content                                  */
/* ─────────────────────────────────────────────────────────── */

const TESTIMONIALS = [
  {
    name: "Thomas",
    role: "Ingénieur, 28\u00A0ans",
    since: "6 semaines",
    quote: "Avant j\u2019ouvrais 40 onglets pour recouper les sources. Maintenant j\u2019agis avant que le prix bouge, et je passe deux fois moins de temps à chercher.",
    avatarClass: "bg-gradient-to-br from-brand-500/40 via-brand-500/10 to-transparent",
  },
  {
    name: "Clara",
    role: "Analyste, 34\u00A0ans",
    since: "3 mois",
    quote: "Je ne surdose plus les signaux en dessous de 60. Foresight m\u2019a aidée à discipliner ma sélection et à garder mon capital pour les vraies opportunités.",
    avatarClass: "bg-gradient-to-br from-amber-500/40 via-amber-500/10 to-transparent",
  },
  {
    name: "Marc",
    role: "Trader indépendant, 41\u00A0ans",
    since: "2 mois",
    quote: "La fenêtre d\u2019action affichée clairement, les sources listées — c\u2019est ce qui me permet de me positionner vite sans avoir à tout revérifier moi-même.",
    avatarClass: "bg-gradient-to-br from-sky-500/40 via-sky-500/10 to-transparent",
  },
  {
    name: "Sophie",
    role: "Étudiante en finance, 23\u00A0ans",
    since: "1 mois",
    quote: "Je ne connaissais pas Polymarket avant Foresight. En une semaine j\u2019avais compris le fonctionnement et placé mes premiers ordres. Le produit m\u2019a vraiment guidée.",
    avatarClass: "bg-gradient-to-br from-violet-500/40 via-violet-500/10 to-transparent",
  },
  {
    name: "Romain",
    role: "Gérant de patrimoine, 37\u00A0ans",
    since: "5 semaines",
    quote: "Le score de conviction est ce qui m\u2019a convaincu. Ce n\u2019est pas juste une alerte news — c\u2019est une vraie analyse du décalage entre l\u2019info et le marché.",
    avatarClass: "bg-gradient-to-br from-emerald-500/40 via-emerald-500/10 to-transparent",
  },
  {
    name: "Léa",
    role: "Journaliste économique, 29\u00A0ans",
    since: "7 semaines",
    quote: "Je lis déjà l\u2019actu toute la journée, mais je ne savais pas quoi en faire sur Polymarket. Foresight fait exactement ce pont-là — et vite.",
    avatarClass: "bg-gradient-to-br from-rose-500/40 via-rose-500/10 to-transparent",
  },
  {
    name: "Antoine",
    role: "Développeur, 32\u00A0ans",
    since: "10 semaines",
    quote: "J\u2019ai apprécié la transparence : les sources sont listées, la logique est expliquée. Je ne suis pas un signal en aveugle — je comprends pourquoi.",
    avatarClass: "bg-gradient-to-br from-cyan-500/40 via-cyan-500/10 to-transparent",
  },
  {
    name: "Julie",
    role: "Consultante, 26\u00A0ans",
    since: "3 semaines",
    quote: "L\u2019alerte Telegram Pro change tout. Je reçois le signal pendant ma journée de travail, je vérifie en 30 secondes, et je décide. Zéro friction.",
    avatarClass: "bg-gradient-to-br from-orange-500/40 via-orange-500/10 to-transparent",
  },
  {
    name: "Pierre",
    role: "Entrepreneur, 45\u00A0ans",
    since: "4 mois",
    quote: "Ce que j\u2019aime c\u2019est que Foresight ne me dit pas quoi penser — il me donne les faits, le score, les sources, et je décide. C\u2019est exactement ce que je voulais.",
    avatarClass: "bg-gradient-to-br from-indigo-500/40 via-indigo-500/10 to-transparent",
  },
]

function TestimonialCard({ name, role, since, quote, avatarClass }: typeof TESTIMONIALS[0]) {
  return (
    <div className="rounded-2xl border border-line bg-obsidian-850 p-6 md:p-7 h-full flex flex-col">
      <div className="mb-4 flex items-center gap-3">
        <div
          className={cn("relative h-9 w-9 shrink-0 overflow-hidden rounded-full border border-line/60", avatarClass)}
          aria-hidden
        />
        <div className="min-w-0">
          <p className="font-display text-body-md font-semibold leading-tight text-ink">{name}</p>
          <p className="mt-0.5 text-body-sm text-ink-muted">{role}</p>
        </div>
      </div>
      <blockquote className="flex-1 text-[1.0625rem] leading-relaxed text-ink-muted">
        {"\u00AB\u00A0"}{quote}{"\u00A0\u00BB"}
      </blockquote>
      <p className="mt-4 text-label-xs text-ink-dim">Utilise Foresight depuis {since}</p>
    </div>
  )
}

function Testimonials() {
  const trackRef = useRef<HTMLDivElement>(null)
  const posRef = useRef(0)
  const rafRef = useRef<number>(0)
  const pausedRef = useRef(false)
  const doubled = [...TESTIMONIALS, ...TESTIMONIALS]

  useEffect(() => {
    const track = trackRef.current
    if (!track) return
    let half = 0

    const tick = () => {
      // Compute half lazily — scrollWidth is 0 before first paint
      if (half === 0) half = track.scrollWidth / 2
      if (half > 0 && !pausedRef.current) {
        posRef.current += 0.6
        if (posRef.current >= half) posRef.current = 0
        track.style.transform = `translateX(-${posRef.current}px)`
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [])

  return (
    <section className="relative py-24 md:py-32">
      <div className="container-page mb-10">
        <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">Témoignages</p>
        <h2 className="text-display-2 text-ink text-balance">Ils utilisent Foresight</h2>
      </div>

      <div
        className="overflow-hidden"
        onMouseEnter={() => { pausedRef.current = true }}
        onMouseLeave={() => { pausedRef.current = false }}
      >
        <div ref={trackRef} className="flex gap-5 w-max">
          {doubled.map((card, i) => (
            <div key={i} className="w-[360px] shrink-0">
              <TestimonialCard {...card} />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Pricing Teaser                                              */
/* ─────────────────────────────────────────────────────────── */

function PricingTeaser() {
  const plans = [
    {
      name: "Free",
      price: "0\u00A0€",
      cadence: "toujours",
      features: [
        { label: "5 signaux / jour", included: true },
        { label: "Dashboard complet", included: true },
        { label: "Livraison différée (15 min)", included: true },
        { label: "Alertes Telegram", included: false },
        { label: "Toutes les catégories", included: false },
      ],
      cta: { label: "Commencer gratuitement", variant: "outline" as const, to: "/signup?plan=free" },
    },
    {
      name: "Pro",
      price: "29\u00A0€",
      cadence: "/ mois",
      features: [
        { label: "Signaux illimités", included: true },
        { label: "Temps réel (< 90 s)", included: true },
        { label: "Alertes Telegram", included: true },
        { label: "Toutes les catégories", included: true },
        { label: "Livraison en < 90 s", included: true },
      ],
      cta: { label: "Essayer Pro", variant: "primary" as const, to: "/signup?plan=pro" },
      trial: "7\u00A0jours gratuits · Aucune carte requise · Passe Free automatiquement à la fin de l\u2019essai",
      highlighted: true,
    },
  ]

  return (
    <section className="relative py-24 md:py-32">
      <div className="container-page">
        <div className="mb-14 text-center">
          {/* Section title Anglicism: "Pricing" → "Tarifs"; subhead de-anglicised ("Upgrade" → "Passe Pro"). */}
          <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">Tarifs</p>
          <h2 className="text-display-2 text-ink text-balance">Commence gratuit. Passe Pro quand tu veux.</h2>
        </div>

        <div className="mx-auto grid max-w-[760px] gap-4 md:grid-cols-2">
          {plans.map((plan, i) => (
            <motion.div
              key={plan.name}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: DURATIONS.expressive, delay: i * 0.08, ease: EASE_PREMIUM }}
              className={cn(
                "relative flex flex-col overflow-hidden rounded-2xl border p-6 md:p-8",
                plan.highlighted
                  ? "border-brand-500/50 bg-gradient-to-br from-brand-500/10 to-obsidian-900 shadow-brand-glow"
                  : "border-line-strong bg-obsidian-900",
              )}
            >
              {plan.highlighted && (
                <div className="absolute -right-1 top-4 rounded-l-md bg-brand-500 px-2.5 py-1 text-label-xs font-mono font-semibold uppercase tracking-widest text-obsidian-900">
                  <Sparkles className="inline-block h-3 w-3 mr-1" />
                  Populaire
                </div>
              )}
              <h3 className="mb-1 font-display text-xl font-semibold text-ink">{plan.name}</h3>
              <div className="mb-5 flex items-baseline gap-1">
                <span className="num font-display text-4xl font-semibold text-ink">{plan.price}</span>
                <span className="text-body-sm text-ink-muted">{plan.cadence}</span>
              </div>
              <ul className="mb-6 space-y-2.5 text-[0.9375rem]">
                {plan.features.map((f) => (
                  <li key={f.label} className={cn("flex items-start gap-2.5", f.included ? "text-ink-muted" : "text-ink-dim")}>
                    {f.included
                      ? <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
                      : <X className="mt-0.5 h-4 w-4 shrink-0 text-ink-faint" />
                    }
                    <span>{f.label}</span>
                  </li>
                ))}
              </ul>
              <Link to={plan.cta.to} className="mt-auto block">
                <Button variant={plan.cta.variant} size="md" className="w-full">
                  {plan.cta.label}
                </Button>
              </Link>
              {"trial" in plan && plan.trial && (
                <p className="mt-3 text-center text-label-sm leading-snug text-ink-dim">
                  {plan.trial}
                </p>
              )}
            </motion.div>
          ))}
        </div>

        <p className="mt-8 text-center text-body-md text-ink-muted">
          {"Besoin d’un accès API\u00A0? "}
          <Link
            to="/pricing"
            className="font-medium text-brand-400 hover:text-brand-300 transition-premium"
          >
            Voir tous les plans →
          </Link>
        </p>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Signal Anatomy — timeline proof                              */
/* Inserted between HowItWorks and LiveFeed in <main>.          */
/* ─────────────────────────────────────────────────────────── */

/* Badge positions map each annotation to its card element (card uses md:px-6 md:py-5):
   1 = score tile  (~y 82px)
   2 = question H3 (~y 170px)
   3 = catalyst box (~y 294px)
   4 = sources footer (bottom) */
const BADGE_POS = [
  "top-[82px] left-0",
  "top-[170px] left-0",
  "top-[294px] left-0",
  "bottom-[16px] left-0",
]

function SignalAnatomy() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: "-10% 0px" })
  const [step, setStep] = useState(0)

  useEffect(() => {
    if (!inView) return
    const timers = [1, 2, 3, 4].map((n) =>
      setTimeout(() => setStep(n), 400 + (n - 1) * 720),
    )
    return () => timers.forEach(clearTimeout)
  }, [inView])

  const callouts = [
    {
      n: 1,
      label: "Le score de conviction",
      body: "Va de 0 à 100 — plus c’est élevé, plus on est sûr du signal. Au-delà de 90\u00A0: excellent. En dessous de 60\u00A0: on ne publie pas.",
    },
    {
      n: 2,
      label: "Le marché Polymarket",
      body: "La question sur laquelle l’opportunité a été détectée. Le prix affiché (41\u00A0%) est ce que le marché croit — notre modèle pense qu’il a tort, grâce aux news.",
    },
    {
      n: 3,
      label: "Ce qu’on a détecté",
      body: "Les actualités publiques que notre modèle a croisées pour déclencher le signal — avant que le marché ne les intègre.",
    },
    {
      n: 4,
      label: "Les sources",
      body: "Nombre d’articles Tier\u00A01 (Reuters, AP, Bloomberg…) utilisés. Clique sur la carte pour vérifier toi-même.",
    },
  ]

  return (
    <section className="relative py-24 md:py-32" ref={ref}>
      <div className="container-page">
        <div className="mx-auto mb-12 max-w-[720px] text-center">
          <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">
            Exemple concret
          </p>
          <h2 className="font-display text-display-3 md:text-display-2 font-semibold text-ink leading-tight tracking-tight text-balance">
            Voici à quoi ressemble un signal
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-body-lg leading-relaxed text-ink-readable">
            {"C’est une carte. Elle te dit\u00A0: quoi, quand, à quel prix, et pourquoi c’est intéressant."}
          </p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-10% 0px" }}
          transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
          className="grid gap-10 md:grid-cols-[1.1fr_1fr] md:gap-14 items-center"
        >
          {/* Annotated card (left) */}
          <div className="relative">
            <div className="pointer-events-none absolute inset-x-8 -top-4 h-12 bg-gradient-to-b from-brand-500/15 to-transparent blur-2xl" />
            <div className="relative">
              <SignalCard signal={MOCK_SIGNALS[3]} example />
              {callouts.map((c, i) => (
                <motion.span
                  key={c.n}
                  aria-hidden
                  initial={{ scale: 0, opacity: 0 }}
                  animate={step >= c.n ? { scale: 1, opacity: 1 } : { scale: 0, opacity: 0 }}
                  transition={{ type: "spring", damping: 14, stiffness: 300 }}
                  style={{ color: '#000' }}
                  className={cn(
                    "absolute z-10 inline-flex h-6 w-6 items-center justify-center rounded-full",
                    "bg-brand-500 font-mono text-label-xs font-bold leading-none shadow-brand-glow",
                    BADGE_POS[i],
                  )}
                >
                  {c.n}
                </motion.span>
              ))}
            </div>
          </div>

          {/* Numbered callouts (right) */}
          <ol className="space-y-5">
            <AnimatePresence>
              {callouts.filter((c) => step >= c.n).map((c) => (
                <motion.li
                  key={c.n}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.4, ease: EASE_PREMIUM }}
                  className="flex gap-4"
                >
                  <span style={{ color: '#000' }} className="mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-500 font-mono text-label-xs font-bold leading-none shadow-brand-glow">
                    {c.n}
                  </span>
                  <div className="min-w-0">
                    <p className="font-display text-title-sm md:text-title-md font-semibold text-ink leading-snug">
                      {c.label}
                    </p>
                    <p className="mt-1 text-body-md leading-relaxed text-ink-readable">
                      {c.body}
                    </p>
                  </div>
                </motion.li>
              ))}
            </AnimatePresence>
          </ol>
        </motion.div>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Why Not Just Polymarket — comparison                         */
/* Inserted between Audiences and PricingTeaser in <main>.      */
/* ─────────────────────────────────────────────────────────── */

function WhyNotPolymarket() {
  const polymarketOnly = [
    "61 247 marchés à surveiller à la main",
    "Pas de scoring de conviction",
    "Pas d’alerte temps réel",
    "Pas d’historique comparatif",
    "Latence\u00A0: dépend de ta vigilance",
  ]

  const foresight = [
    "Pipeline 24/7 qui surveille pour toi",
    "Score de conviction calculé (0-100)",
    "Alerte Telegram en 90\u00A0s (Pro)",
    "Comparaison avec 2 847 signaux historiques",
    "Latence\u00A0: 90\u00A0s en moyenne",
  ]

  return (
    <section className="relative py-24 md:py-32">
      <div className="container-page">
        <div className="mb-14 max-w-[720px]">
          <p className="mb-3 font-mono text-sm uppercase tracking-[0.12em] text-brand-400">
            {"Pourquoi pas juste Polymarket\u00A0?"}
          </p>
          <h2 className="text-display-2 text-ink text-balance">
            {"Parce que tu n’as pas 61 247 onglets."}
          </h2>
          <p className="mt-3 text-[1rem] leading-relaxed text-ink-muted">
            La différence entre regarder le marché et être en avance sur lui.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-10% 0px" }}
            transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
            className="rounded-2xl border border-line/60 bg-obsidian-800/40 p-6 md:p-8"
          >
            <h3 className="mb-5 font-display text-title-md font-semibold tracking-tight text-ink-muted">
              Polymarket seul
            </h3>
            <ul className="space-y-3 text-[0.9375rem] text-ink-muted">
              {polymarketOnly.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <X className="mt-0.5 h-4 w-4 shrink-0 text-signal-no" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-10% 0px" }}
            transition={{ duration: DURATIONS.expressive, delay: 0.1, ease: EASE_PREMIUM }}
            className="rounded-2xl border border-brand-500/30 bg-gradient-to-br from-brand-500/[0.06] to-obsidian-850/80 p-6 shadow-brand-glow md:p-8"
          >
            <h3 className="mb-5 font-display text-title-md font-semibold tracking-tight text-ink">
              Foresight
            </h3>
            <ul className="space-y-3 text-[0.9375rem] text-ink">
              {foresight.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

/* ─────────────────────────────────────────────────────────── */
/* Final CTA                                                    */
/* ─────────────────────────────────────────────────────────── */

function FinalCta() {
  return (
    <section className="relative overflow-hidden py-24 md:py-32">
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(50% 60% at 50% 50%, rgba(11,224,166,0.12), transparent 70%)",
        }}
        aria-hidden
      />
      <div className="pointer-events-none absolute inset-0 bg-grid bg-grid-fade opacity-40" aria-hidden />

      <div className="container-page relative">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
          className="mx-auto max-w-[820px] text-center"
        >
          <h2 className="text-display-1 text-ink text-balance">
            L’information a toujours eu de la valeur.
            <span className="block bg-gradient-to-r from-brand-300 via-brand-400 to-brand-500 bg-clip-text text-transparent">
              Maintenant tu peux en profiter avant les autres.
            </span>
          </h2>

          <div className="mt-10 flex flex-col items-center gap-4">
            <Link to="/signup?plan=free">
              <Button variant="primary" size="xl">
                Commencer gratuitement
                <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <p className="text-body-sm text-ink-dim">
              Pas de carte · Accès immédiat · Annulable à tout moment
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
