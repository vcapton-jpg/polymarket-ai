import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Check, Zap, Crown, Building2, ExternalLink, Loader2, CreditCard, Shield } from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { cn } from "../lib/utils"
import { TOKEN_KEY } from "../lib/authStorage"

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.4 },
  }),
}

const sectionFade = {
  hidden: { opacity: 0, y: 14 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] as const, delay: 0.35 },
  },
}

const PLANS = [
  {
    key: "free",
    name: "Gratuit",
    price: 0,
    icon: Zap,
    color: "#6B7280",
    popular: false,
    features: [
      "5 signaux par jour",
      "Score et direction",
      "Dernieres 24h",
      "Dashboard basique",
    ],
  },
  {
    key: "pro",
    name: "Pro",
    price: 29,
    icon: Crown,
    color: "#F59E0B",
    popular: true,
    features: [
      "Signaux illimites",
      "Explications detaillees",
      "Historique complet",
      "Alertes Telegram & Push",
      "Dashboard performance",
      "Support prioritaire",
    ],
  },
  {
    key: "trader",
    name: "Trader",
    price: 99,
    icon: Building2,
    color: "#8B5CF6",
    popular: false,
    features: [
      "Tout Pro inclus",
      "Execution Polymarket",
      "Alertes risk management",
      "Briefs quotidiens",
      "API access (10k req/jour)",
      "Support dedie",
    ],
  },
]

export default function Pricing() {
  const nav = useNavigate()
  const [loadingPlan, setLoadingPlan] = useState<string | null>(null)

  const handleUpgrade = async (plan: string) => {
    setLoadingPlan(plan)
    try {
      const token = localStorage.getItem(TOKEN_KEY)
      const res = await fetch(`/api/subscriptions/checkout?plan=${plan}`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      } else {
        alert(data.detail || "Stripe non configure. Bientot disponible !")
      }
    } catch {
      alert("Erreur de connexion. Reessayez.")
    } finally {
      setLoadingPlan(null)
    }
  }

  const handleManage = async () => {
    try {
      const token = localStorage.getItem(TOKEN_KEY)
      const res = await fetch(`/api/subscriptions/portal`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const data = await res.json()
      if (data.portal_url) {
        window.location.href = data.portal_url
      }
    } catch {
      alert("Erreur de connexion.")
    }
  }

  return (
    <div className="max-w-[960px] mx-auto">
      <PageHeader
        title="Tarifs"
        subtitle="Commencez gratuitement, evoluez quand vous etes pret"
      />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-8">
        {PLANS.map((plan, i) => (
          <motion.div
            key={plan.key}
            initial="hidden"
            animate="visible"
            variants={fadeUp}
            custom={i}
          >
            <div
              className={cn(
                "h-full rounded-xl",
                plan.popular && "gradient-border shadow-glow",
              )}
            >
              <Card
                className={cn(
                  "p-6 relative overflow-hidden h-full flex flex-col glass-card-hover",
                  plan.popular && "border-transparent shadow-card-hover",
                )}
              >
                {plan.popular && (
                  <div className="absolute -top-0 right-0 bg-gradient-to-r from-accent to-accent-bright text-surface-0 text-[10px] font-bold px-3 py-1.5 rounded-bl-xl font-display tracking-wide">
                    POPULAIRE
                  </div>
                )}

                <div className="flex items-center gap-3 mb-5">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center border border-edge-subtle shadow-inner-glow"
                    style={{ background: `${plan.color}15`, color: plan.color }}
                  >
                    <plan.icon size={22} />
                  </div>
                  <h3 className="text-lg font-bold text-txt-primary font-display tracking-display">
                    {plan.name}
                  </h3>
                </div>

                <div className="mb-6">
                  <span className="text-3xl font-extrabold text-txt-primary font-mono">
                    {plan.price}€
                  </span>
                  {plan.price > 0 ? (
                    <span className="text-sm text-txt-muted">/mois</span>
                  ) : (
                    <span className="text-sm text-txt-muted ml-1">pour toujours</span>
                  )}
                </div>

                <div className="flex flex-col gap-2.5 mb-7 flex-1">
                  {plan.features.map((f) => (
                    <div key={f} className="flex items-start gap-2.5">
                      <Check size={14} className="text-success shrink-0 mt-0.5" />
                      <span className="text-sm text-txt-secondary">{f}</span>
                    </div>
                  ))}
                </div>

                {plan.key === "free" ? (
                  <div className="text-center py-2.5 px-4 rounded-xl bg-surface-raised border border-edge-subtle text-txt-muted text-sm font-medium font-mono">
                    Plan actuel
                  </div>
                ) : (
                  <button
                    onClick={() => handleUpgrade(plan.key)}
                    disabled={loadingPlan === plan.key}
                    className={cn(
                      "w-full py-3 rounded-lg text-sm font-bold transition-all cursor-pointer border-none flex items-center justify-center gap-2 font-display",
                      plan.popular
                        ? "bg-gradient-to-r from-accent to-accent-bright text-surface-0 shadow-glow hover:shadow-glow-lg hover:brightness-105"
                        : "bg-surface-raised text-txt-secondary hover:text-accent border border-edge-subtle hover:border-accent/25 shadow-card hover:shadow-card-hover",
                      loadingPlan === plan.key && "opacity-50 cursor-not-allowed",
                    )}
                  >
                    {loadingPlan === plan.key ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      `Passer a ${plan.name}`
                    )}
                  </button>
                )}
              </Card>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Payment methods */}
      <motion.div initial="hidden" animate="visible" variants={sectionFade}>
        <Card className="p-5 mb-5 shadow-glass">
          <div className="flex items-center gap-3 mb-3">
            <Shield size={16} className="text-success" />
            <h3 className="text-sm font-semibold text-txt-primary font-display tracking-display">
              Paiement securise
            </h3>
          </div>
          <p className="text-xs text-txt-muted mb-4">
            Paiements geres par Stripe. Vos donnees bancaires ne transitent jamais par nos serveurs.
          </p>
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-raised border border-edge-subtle text-txt-secondary text-xs font-medium font-mono">
              <CreditCard size={14} />
              Carte bancaire
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-raised text-xs font-medium border border-edge-subtle" style={{ color: "#000", background: "#fff" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M17.05 20.28c-.98.95-2.05.88-3.08.4-1.09-.5-2.08-.48-3.24 0-1.44.62-2.2.44-3.06-.4C2.79 15.25 3.51 7.59 9.05 7.31c1.35.07 2.29.74 3.08.8 1.18-.24 2.31-.93 3.57-.84 1.51.12 2.65.72 3.4 1.8-3.12 1.87-2.38 5.98.48 7.13-.57 1.5-1.31 2.99-2.53 4.09zM12.03 7.25c-.15-2.23 1.66-4.07 3.74-4.25.29 2.58-2.34 4.5-3.74 4.25z"/></svg>
              Apple Pay
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-raised text-xs font-medium border border-edge-subtle" style={{ color: "#fff", background: "#4285f4" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
              Google Pay
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-surface-raised text-xs font-medium border border-edge-subtle" style={{ color: "#635bff" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M13.976 9.15c-2.172-.806-3.356-1.426-3.356-2.409 0-.831.683-1.305 1.901-1.305 2.227 0 4.515.858 6.09 1.631l.89-5.494C18.252.975 15.697 0 12.165 0 9.667 0 7.589.654 6.104 1.872 4.56 3.147 3.757 4.992 3.757 7.218c0 4.039 2.467 5.76 6.476 7.219 2.585.92 3.445 1.574 3.445 2.583 0 .98-.84 1.545-2.354 1.545-1.875 0-4.965-.921-6.99-2.109l-.9 5.555C5.175 22.99 8.385 24 11.714 24c2.641 0 4.843-.624 6.328-1.813 1.664-1.305 2.525-3.236 2.525-5.732 0-4.128-2.524-5.851-6.591-7.305z"/></svg>
              Link
            </div>
          </div>
        </Card>
      </motion.div>

      {/* Manage subscription */}
      <motion.div initial="hidden" animate="visible" variants={sectionFade}>
        <Card className="p-5 flex items-center justify-between flex-wrap gap-4 shadow-glass">
          <div>
            <h3 className="text-sm font-semibold text-txt-primary mb-1 font-display tracking-display">
              Gerer votre abonnement
            </h3>
            <p className="text-xs text-txt-muted">
              Modifier votre plan, mettre a jour le moyen de paiement, ou annuler via le portail Stripe.
            </p>
          </div>
          <button
            onClick={handleManage}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-raised border border-edge-subtle text-txt-secondary text-sm font-medium hover:text-accent hover:border-accent/20 transition-colors cursor-pointer shadow-card hover:shadow-card-hover"
          >
            <ExternalLink size={14} />
            Portail client
          </button>
        </Card>
      </motion.div>
    </div>
  )
}
