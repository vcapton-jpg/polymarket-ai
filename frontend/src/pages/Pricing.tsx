import { useQuery } from "@tanstack/react-query"
import { motion } from "framer-motion"
import { Check, X, Zap, Crown, Building2 } from "lucide-react"
import { PageHeader } from "../components/layout/PageHeader"
import { Card } from "../components/ui/Card"
import { Button } from "../components/ui/Button"
import { api, queryKeys } from "../lib/api"
import { cn } from "../lib/utils"

const PLAN_ICONS: Record<string, React.ReactNode> = {
  free: <Zap size={24} />,
  pro: <Crown size={24} />,
  enterprise: <Building2 size={24} />,
}

const PLAN_COLORS: Record<string, string> = {
  free: "#6b7280",
  pro: "#3b82f6",
  enterprise: "#a855f7",
}

const FEATURES = [
  { key: "signals_per_day", label: "Signals per day", format: (v: number) => v === -1 ? "Unlimited" : String(v) },
  { key: "execution", label: "Trade execution" },
  { key: "risk_alerts", label: "Risk alerts" },
  { key: "daily_briefs", label: "Daily intelligence briefs" },
  { key: "api_access", label: "B2B API access" },
]

export default function Pricing() {
  const { data: plansData } = useQuery({
    queryKey: queryKeys.plans,
    queryFn: () => api.plans(),
  })

  const { data: currentData } = useQuery({
    queryKey: queryKeys.currentPlan,
    queryFn: () => api.currentPlan(),
  })

  const plans = plansData?.plans || {}
  const currentPlan = currentData?.plan || "free"

  const handleUpgrade = async (plan: string) => {
    try {
      const res = await fetch("/api/subscriptions/checkout?plan=" + plan, { method: "POST" })
      const data = await res.json()
      if (data.checkout_url) {
        window.location.href = data.checkout_url
      }
    } catch {
      alert("Stripe not configured yet. Coming soon!")
    }
  }

  return (
    <div>
      <PageHeader title="Pricing" subtitle="Choose the plan that fits your trading style" />

      <div className="grid md:grid-cols-3 gap-5 mb-8">
        {Object.entries(plans).map(([key, plan], i) => {
          const isCurrent = key === currentPlan
          const color = PLAN_COLORS[key] || "#888"

          return (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card
                className={cn(
                  "p-6 relative overflow-hidden",
                  key === "pro" && "ring-1 ring-accent/30",
                )}
              >
                {key === "pro" && (
                  <div className="absolute top-0 right-0 bg-accent text-white text-[10px] font-bold px-3 py-1 rounded-bl-lg">
                    POPULAR
                  </div>
                )}
                <div className="flex items-center gap-3 mb-4">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{ background: `${color}20`, color }}
                  >
                    {PLAN_ICONS[key]}
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-txt-primary">{plan.name}</h3>
                    <p className="text-sm text-txt-muted">
                      {plan.price === 0 ? "Free forever" : `$${plan.price}/month`}
                    </p>
                  </div>
                </div>

                <div className="mb-5">
                  <span className="text-3xl font-bold text-txt-primary font-mono">
                    ${plan.price}
                  </span>
                  {plan.price > 0 && (
                    <span className="text-sm text-txt-muted">/mo</span>
                  )}
                </div>

                <div className="flex flex-col gap-2.5 mb-6">
                  {FEATURES.map(({ key: fKey, label, format }) => {
                    const val = (plan as any)[fKey]
                    const enabled = typeof val === "boolean" ? val : val !== 0

                    return (
                      <div key={fKey} className="flex items-center gap-2.5">
                        {enabled ? (
                          <Check size={14} className="text-success shrink-0" />
                        ) : (
                          <X size={14} className="text-txt-muted/40 shrink-0" />
                        )}
                        <span className={cn(
                          "text-sm",
                          enabled ? "text-txt-secondary" : "text-txt-muted/50",
                        )}>
                          {format ? format(val) : label}
                          {!format && enabled && typeof val === "number" && val > 0 && ` (${val})`}
                          {!format && label}
                        </span>
                      </div>
                    )
                  })}
                </div>

                {isCurrent ? (
                  <div className="text-center py-2 px-4 rounded-md bg-surface-raised text-txt-muted text-sm font-medium">
                    Current plan
                  </div>
                ) : key === "free" ? (
                  <div className="text-center py-2 px-4 rounded-md bg-surface-raised text-txt-muted text-sm font-medium">
                    Free tier
                  </div>
                ) : (
                  <Button
                    className="w-full"
                    onClick={() => handleUpgrade(key)}
                    style={{ background: color }}
                  >
                    Upgrade to {plan.name}
                  </Button>
                )}
              </Card>
            </motion.div>
          )
        })}
      </div>

      <Card className="p-6">
        <h3 className="text-sm font-semibold text-txt-primary mb-2">Volume Rewards</h3>
        <p className="text-sm text-txt-muted leading-relaxed">
          Every trade executed through Signal earns USDC rewards from Polymarket's Builder Program.
          The more you trade, the more the platform earns — and the better the agents become.
          Pro and Enterprise users benefit from enhanced execution and priority features funded
          by these rewards.
        </p>
      </Card>
    </div>
  )
}
