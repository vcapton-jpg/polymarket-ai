import { Link } from "react-router-dom"
import { motion } from "framer-motion"
import { EASE_PREMIUM, DURATIONS } from "@/lib/motion"
import { useEffect, useState } from "react"
import { ArrowRight, Check, Shield, Sparkles, Zap } from "lucide-react"
import { PublicNav } from "@/components/layout/PublicNav"
import { Footer } from "@/components/layout/Footer"
import { Button } from "@/components/ui/Button"
import { PoweredByPolymarket } from "@/components/signals/PoweredByPolymarket"
import { cn } from "@/lib/utils"
import { useAuth } from "@/hooks/useAuth"
import { safeStartCheckout, type PlanKey } from "@/lib/api/subscriptions"

const PRICING_CYCLE_KEY = "foresight.pricing_cycle"

type Plan = {
  name: string
  monthly: number
  annual: number
  tagline: string
  features: string[]
  /** `to` may be an internal route (`/signup?plan=...`) or an external href
   *  (e.g. `mailto:`). The renderer picks `<Link>` vs `<a>` based on scheme. */
  cta: { label: string; to: string; variant: "primary" | "outline" | "secondary" }
  highlighted?: boolean
}

/**
 * Pivot L&T pricing: two consumer tiers (Free, Pro) aligned to the
 * education-first positioning. Free unlocks paper trading + the
 * onboarding loop; Pro raises real-money caps and opens the unlimited
 * feed. The legacy API tier was dropped here — B2B integrations will
 * ship via a dedicated contact flow once the consumer funnel is stable.
 */
const PLANS: Plan[] = [
  {
    name: "Free",
    monthly: 0,
    annual: 0,
    tagline: "Pour apprendre, sans risque.",
    features: [
      "Paper trading illimité",
      "Tutoriel + quiz risque",
      "Feed signaux (10/jour)",
      "Outcome explainer après résolution",
      "Budget hebdo max\u00A0: 20\u00A0€ réel",
      "Mise max par trade\u00A0: 5\u00A0€",
    ],
    cta: { label: "Commencer gratuit", to: "/signup?plan=free", variant: "outline" },
  },
  {
    name: "Pro",
    monthly: 9,
    annual: 79,
    tagline: "Pour trader sérieusement, avec des limites saines.",
    features: [
      "Tout le Free",
      "Feed illimité (temps réel)",
      "Analytics avancés (winrate, baselines, edges)",
      "Alertes push temps réel",
      "Budget hebdo max\u00A0: 200\u00A0€ réel",
      "Mise max par trade\u00A0: 50\u00A0€",
      "Historique paper + réel exportable CSV",
    ],
    cta: { label: "Passer Pro", to: "/signup?plan=pro", variant: "primary" },
    highlighted: true,
  },
]

export default function Pricing() {
  const [annual, setAnnual] = useState<boolean>(() => {
    if (typeof window === "undefined") return false
    try {
      return window.localStorage.getItem(PRICING_CYCLE_KEY) === "annual"
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(PRICING_CYCLE_KEY, annual ? "annual" : "monthly")
    } catch {
      // ignore persistence failures (private mode / quota)
    }
  }, [annual])

  return (
    <>
      <PublicNav />
      <main className="relative pt-32 pb-24 md:pt-40 md:pb-32">
        <div className="pointer-events-none absolute inset-x-0 top-0 h-[500px] bg-grid bg-grid-fade opacity-40" aria-hidden />
        <div
          className="pointer-events-none absolute inset-x-0 top-0 h-[500px]"
          style={{ background: "radial-gradient(50% 50% at 50% 0%, rgba(11,224,166,0.12), transparent 70%)" }}
          aria-hidden
        />

        <div className="container-page relative">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: DURATIONS.expressive, ease: EASE_PREMIUM }}
            className="mx-auto max-w-[720px] text-center"
          >
            {/* Eyebrow "Pricing" preserved per voice-guide exception. H1 + subhead reworded & de-anglicised. */}
            <p className="mb-3 font-mono text-eyebrow uppercase text-brand-400">Pricing</p>
            <h1 className="text-display-1 text-ink text-balance">
              {"Le prix d’un café par jour."}{" "}
              <span className="bg-gradient-to-r from-brand-300 to-brand-500 bg-clip-text text-transparent">
                Zéro engagement.
              </span>
            </h1>
            <p className="mt-6 text-lg text-ink-muted">
              Commence gratuit. Passe Pro quand tu veux. Annulable à tout moment.
            </p>

            <div className="mt-10 inline-flex items-center gap-1 rounded-full border border-line-strong bg-obsidian-800/70 p-1 backdrop-blur">
              <BillingToggle active={!annual} onClick={() => setAnnual(false)}>
                Mensuel
              </BillingToggle>
              <BillingToggle active={annual} onClick={() => setAnnual(true)}>
                Annuel
                <span className="ml-1.5 rounded px-1.5 py-0.5 bg-brand-500/15 text-[0.625rem] font-mono font-medium text-brand-300 tracking-wider">
                  -2 MOIS
                </span>
              </BillingToggle>
            </div>
          </motion.div>

          <div className="mt-14 grid gap-5 md:grid-cols-2 md:max-w-3xl md:mx-auto">
            {PLANS.map((plan, i) => (
              <PricingCard
                key={plan.name}
                plan={plan}
                index={i}
                annual={annual}
              />
            ))}
          </div>

          <p className="mt-10 text-center text-body-sm text-ink-muted">
            <Check className="inline-block h-3.5 w-3.5 mr-1 text-brand-400 align-text-bottom" />
            Annulable à tout moment
            <span className="mx-3 text-line-strong">·</span>
            <Check className="inline-block h-3.5 w-3.5 mr-1 text-brand-400 align-text-bottom" />
            Pas d’engagement
            <span className="mx-3 text-line-strong">·</span>
            <Check className="inline-block h-3.5 w-3.5 mr-1 text-brand-400 align-text-bottom" />
            Paiement sécurisé
          </p>

          {/* Trust anchor — Polymarket partnership badge lifted onto Pricing
              (Fix 13) so the value prop sits right under the plan grid. */}
          <div className="mt-6 flex justify-center">
            <PoweredByPolymarket size="sm" />
          </div>

          {/* Feature comparison / FAQ light */}
          <div className="mt-24">
            <div className="mb-10 text-center">
              <p className="mb-3 font-mono text-eyebrow uppercase text-brand-400">Questions fréquentes</p>
              <h2 className="text-display-3 text-ink">Tout ce qu’il te faut savoir.</h2>
            </div>

            <div className="mx-auto max-w-[820px] divide-y divide-line/60 rounded-2xl border border-line-strong bg-obsidian-850/40">
              <Faq
                q={"Je peux vraiment commencer sans carte bancaire\u00A0?"}
                a={"Oui. Le plan Free te donne 5 signaux par jour, accès complet au dashboard et à l’historique. Tu passes Pro quand tu veux."}
              />
              <Faq
                q={"Puis-je annuler à tout moment\u00A0?"}
                a={"Oui — en un clic dans Réglages · Plan. Tu gardes l\u2019accès Pro jusqu\u2019à la fin de la période payée, puis tu repasses en Free sans interruption."}
              />
              <Faq
                q={"Qu’est-ce qui se passe si j’annule\u00A0?"}
                a="Tu gardes tes données et ton historique. Ton compte retombe sur le plan Free à la fin de la période payée."
              />
              <Faq
                q={"Comment marche la facturation annuelle\u00A0?"}
                a={"Tu payes 10 mois, tu en obtiens 12. Soit 290\u00A0€/an pour Pro (au lieu de 348\u00A0€) et 990\u00A0€/an pour API (au lieu de 1\u00A0188\u00A0€)."}
              />
              <Faq
                q={"Le plan API est pour qui\u00A0?"}
                a="Pour les traders qui intègrent les signaux dans leur propre système — REST + WebSocket, 10 000 appels par mois, SLA dédié."
              />
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}

function BillingToggle({
  active,
  children,
  onClick,
}: {
  active: boolean
  children: React.ReactNode
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative inline-flex items-center gap-1.5 rounded-full px-4 py-1.5 text-body-sm font-medium transition-premium cursor-pointer",
        active ? "bg-obsidian-700 text-ink shadow-inset-line" : "text-ink-muted hover:text-ink",
      )}
    >
      {children}
    </button>
  )
}

function PricingCard({
  plan,
  index,
  annual,
}: {
  plan: Plan
  index: number
  annual: boolean
}) {
  const auth = useAuth()
  const price = annual ? plan.annual : plan.monthly
  const cadence = annual ? (price === 0 ? "toujours" : "/ an") : price === 0 ? "toujours" : "/ mois"
  const [checkoutError, setCheckoutError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const isUpgradePlan = plan.name === "Pro" || plan.name === "API"
  const planKey: PlanKey | null = isUpgradePlan
    ? plan.name === "Pro"
      ? "pro"
      : null /* API plan is mailto-only, not Stripe */
    : null
  // Authenticated + this plan is a paid one we know how to checkout → skip
  // the /signup path and go straight to Stripe.
  const useStripeCheckout = !!auth && planKey !== null

  async function handleStripeCheckout() {
    if (!planKey) return
    setSubmitting(true)
    setCheckoutError(null)
    const res = await safeStartCheckout(planKey, annual ? "annual" : "monthly")
    if ("url" in res) {
      window.location.assign(res.url)
    } else {
      setCheckoutError(res.error)
      setSubmitting(false)
    }
  }

  return (
    <motion.div
      // Lowercased plan name used as anchor id so links like /pricing#api scroll here.
      id={plan.name.toLowerCase()}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATIONS.expressive, delay: 0.1 + index * 0.08, ease: EASE_PREMIUM }}
      className={cn(
        "relative overflow-hidden rounded-2xl border p-7 md:p-8 scroll-mt-24",
        plan.highlighted
          ? "border-brand-500/50 bg-gradient-to-br from-brand-500/10 via-obsidian-900 to-obsidian-900 shadow-brand-glow"
          : "border-line-strong bg-obsidian-900",
      )}
    >
      {plan.highlighted && (
        <div className="absolute right-0 top-5 flex items-center gap-1 rounded-l-md bg-brand-500 px-3 py-1 text-label-xs font-mono font-semibold uppercase tracking-widest text-obsidian-900">
          <Sparkles className="h-3 w-3" />
          Populaire
        </div>
      )}

      <div className="mb-1 flex items-center gap-2">
        <h3 className="font-display text-[1.375rem] font-semibold text-ink">{plan.name}</h3>
        {plan.highlighted && <Zap className="h-4 w-4 text-brand-400" />}
      </div>
      <p className="mb-3 text-body-md text-ink-muted">{plan.tagline}</p>

      {plan.highlighted && (
        <div className="mb-5 inline-flex items-center rounded-full border border-brand-500/30 bg-brand-500/[0.12] px-2.5 py-1 text-label-xs text-brand-300">
          {"Essai\u00A07\u00A0jours sans engagement · Aucune carte"}
        </div>
      )}

      <div className="mb-2 flex items-baseline gap-1.5">
        {/* NBSP between amount and € per French typography rules. */}
        <span className="num font-display text-5xl font-semibold text-ink">{`${price}\u00A0€`}</span>
        <span className="text-sm text-ink-muted">{cadence}</span>
      </div>

      {/* Strikethrough anchor: annual shows the equivalent monthly ×12 crossed
          out + a savings chip. Monthly mode on Pro still hints at the annual
          total so the comparison is visible before toggling. */}
      {plan.monthly > 0 && (
        <div className="mb-6 flex items-center gap-2 text-body-sm">
          {annual ? (
            <>
              <s className="num text-ink-dim">{`${plan.monthly * 12}\u00A0€`}</s>
              <span className="num text-ink-muted">{`${plan.annual}\u00A0€`}</span>
              <span className="rounded-full border border-brand-500/30 bg-brand-500/10 px-1.5 py-0.5 font-mono text-[0.625rem] uppercase tracking-[0.12em] text-brand-300">
                -17&nbsp;%
              </span>
            </>
          ) : (
            <span className="text-ink-dim">
              {`${plan.monthly}\u00A0€\u00A0× 12 = ${plan.monthly * 12}\u00A0€`}
            </span>
          )}
        </div>
      )}
      {plan.monthly === 0 && <div className="mb-6" />}

      {/* External targets (mailto:, http*) must render as <a> — react-router's
          Link would try to treat them as internal paths. Internal routes
          continue to use <Link> for SPA navigation.
          Authenticated users on a paid plan skip /signup entirely and
          submit a Stripe Checkout session right here. */}
      {useStripeCheckout ? (
        <Button
          variant={plan.cta.variant}
          size="lg"
          className="w-full"
          onClick={handleStripeCheckout}
          disabled={submitting}
        >
          {submitting ? "Redirection…" : plan.cta.label}
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      ) : /^(mailto:|https?:\/\/)/.test(plan.cta.to) ? (
        <a href={plan.cta.to} className="block">
          <Button variant={plan.cta.variant} size="lg" className="w-full">
            {plan.cta.label}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </a>
      ) : (
        <Link to={plan.cta.to} className="block">
          <Button variant={plan.cta.variant} size="lg" className="w-full">
            {plan.cta.label}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>
        </Link>
      )}

      {checkoutError && (
        <p
          role="alert"
          className="mt-2 text-center text-body-sm text-signal-no"
        >
          {checkoutError}
        </p>
      )}

      {plan.highlighted && (
        <p className="mt-2 text-center text-label-xs text-ink-muted">
          {"7\u00A0jours gratuits · Aucune carte requise · Passe Free automatiquement à la fin de l\u2019essai"}
        </p>
      )}

      <div className="my-6 hairline" />

      <ul className="space-y-3 text-[0.9375rem] text-ink-muted">
        {plan.features.map((f) => (
          <li key={f} className="flex items-start gap-2.5">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-brand-400" />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      {plan.highlighted && (
        <p className="mt-5 flex items-start gap-2 text-body-sm text-ink-muted">
          <Shield className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-400" aria-hidden />
          <span>
            Garantie 14{"\u00A0"}jours · Remboursé intégralement si tu n{"\u2019"}es pas convaincu.
          </span>
        </p>
      )}
    </motion.div>
  )
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="group">
      <summary className="flex cursor-pointer items-center justify-between gap-4 px-6 py-5 text-[0.9375rem] font-medium text-ink list-none">
        <span>{q}</span>
        <span className="shrink-0 font-mono text-brand-400 transition-transform group-open:rotate-45">+</span>
      </summary>
      <div className="px-6 pb-5 text-[0.9375rem] leading-relaxed text-ink-muted">{a}</div>
    </details>
  )
}
