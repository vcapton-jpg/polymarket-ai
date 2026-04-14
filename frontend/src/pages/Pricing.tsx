import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { motion } from "framer-motion"
import { Check, Zap, Crown, Building2, ExternalLink, Loader2 } from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { cn } from "../lib/utils"

const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { delay: i * 0.1, duration: 0.4 },
  }),
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
      const token = localStorage.getItem("presage-token")
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
      const token = localStorage.getItem("presage-token")
      const res = await fetch("/api/subscriptions/portal", {
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
            <Card
              className={cn(
                "p-6 relative overflow-hidden h-full flex flex-col",
                plan.popular && "ring-1 ring-accent/30",
              )}
            >
              {plan.popular && (
                <div className="absolute -top-0 right-0 bg-accent text-surface-0 text-[10px] font-bold px-3 py-1.5 rounded-bl-xl">
                  POPULAIRE
                </div>
              )}

              <div className="flex items-center gap-3 mb-5">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{ background: `${plan.color}15`, color: plan.color }}
                >
                  <plan.icon size={22} />
                </div>
                <h3 className="text-lg font-bold text-txt-primary">{plan.name}</h3>
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
                <div className="text-center py-2.5 px-4 rounded-xl bg-surface-raised text-txt-muted text-sm font-medium">
                  Plan actuel
                </div>
              ) : (
                <button
                  onClick={() => handleUpgrade(plan.key)}
                  disabled={loadingPlan === plan.key}
                  className={cn(
                    "w-full py-3 rounded-xl text-sm font-bold transition-all cursor-pointer border-none flex items-center justify-center gap-2",
                    plan.popular
                      ? "bg-accent text-surface-0 hover:brightness-110"
                      : "bg-surface-raised text-txt-secondary hover:text-accent",
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
          </motion.div>
        ))}
      </div>

      {/* Manage subscription */}
      <Card className="p-5 flex items-center justify-between flex-wrap gap-4">
        <div>
          <h3 className="text-sm font-semibold text-txt-primary mb-1">Gerer votre abonnement</h3>
          <p className="text-xs text-txt-muted">
            Modifier votre plan, mettre a jour le moyen de paiement, ou annuler via le portail Stripe.
          </p>
        </div>
        <button
          onClick={handleManage}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-raised text-txt-secondary text-sm font-medium hover:text-accent transition-colors cursor-pointer border-none"
        >
          <ExternalLink size={14} />
          Portail client
        </button>
      </Card>
    </div>
  )
}
