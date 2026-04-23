import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { submitBudget } from "@/lib/api/onboarding"

/**
 * Last gate in the Learn & Trade onboarding sequence (/welcome/budget).
 *
 * User sets:
 * - Weekly budget (5€–200€, step 5€) — hard cap, enforced server-side on every trade
 * - Max stake per trade (1€–50€, step 1€) — capped at ≤ weekly
 * - Age 18+ (mandatory, independent from Signup checkbox)
 * - CGU acceptance (mandatory, independent from Signup checkbox)
 *
 * On success the backend flips `onboarding_progress.budget_done = true`
 * and, if all other gates (tutorial_done + quiz_done + quiz_passed +
 * age_confirmed_18 + cgu_accepted) are met, sets
 * `onboarding_progress.unlocked_real_trading_at`. Then we route to /signals.
 */
export default function BudgetSetup() {
  const [weekly, setWeekly] = useState(20)
  const [maxStake, setMaxStake] = useState(5)
  const [ageOk, setAgeOk] = useState(false)
  const [cguOk, setCguOk] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const navigate = useNavigate()

  async function onSubmit() {
    if (submitting) return
    setErr(null)
    if (maxStake > weekly) {
      setErr("La mise max ne peut pas dépasser le budget hebdomadaire.")
      return
    }
    setSubmitting(true)
    try {
      await submitBudget({
        budgetWeeklyEur: weekly,
        maxStakeEur: maxStake,
        ageConfirmed18: ageOk,
        cguAccepted: cguOk,
      })
      navigate("/signals")
    } catch (e: unknown) {
      setErr(
        e instanceof Error
          ? e.message
          : "Impossible d'enregistrer tes limites — réessaie.",
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-6 space-y-6">
      <h1 className="text-2xl font-bold">Définis tes limites</h1>
      <p className="text-sm text-ink-muted">
        Tu peux modifier ces limites plus tard dans Settings. Elles sont
        appliquées côté serveur sur chaque ordre réel.
      </p>

      <div className="space-y-2">
        <label htmlFor="budget-weekly" className="text-sm font-semibold">
          Budget hebdomadaire (€)
        </label>
        <input
          id="budget-weekly"
          type="range"
          min={5}
          max={200}
          step={5}
          value={weekly}
          onChange={(e) => setWeekly(Number(e.target.value))}
          className="w-full"
          aria-label="Budget hebdomadaire"
        />
        <p className="text-xl font-bold">{weekly}€ / semaine</p>
      </div>

      <div className="space-y-2">
        <label htmlFor="max-stake" className="text-sm font-semibold">
          Mise max par trade (€)
        </label>
        <input
          id="max-stake"
          type="range"
          min={1}
          max={50}
          step={1}
          value={maxStake}
          onChange={(e) => setMaxStake(Number(e.target.value))}
          className="w-full"
          aria-label="Mise max par trade"
        />
        <p className="text-xl font-bold">{maxStake}€ max / trade</p>
      </div>

      <div className="rounded-lg bg-obsidian-850/60 border border-line p-3 text-xs text-ink-muted">
        Règle : tu ne pourras jamais miser plus de {maxStake}€ sur un trade,
        ni plus de {weekly}€ au total sur la semaine glissante. Passée cette
        limite, l'API refuse tes ordres.
      </div>

      <label className="flex items-start gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={ageOk}
          onChange={(e) => setAgeOk(e.target.checked)}
          className="mt-0.5"
        />
        <span>Je confirme avoir 18 ans ou plus.</span>
      </label>
      <label className="flex items-start gap-2 text-sm cursor-pointer">
        <input
          type="checkbox"
          checked={cguOk}
          onChange={(e) => setCguOk(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          J'accepte les{" "}
          <a href="/cgu" target="_blank" rel="noopener noreferrer" className="underline">
            CGU
          </a>{" "}
          et comprends que je peux perdre la totalité de ma mise.
        </span>
      </label>

      {err && <p className="text-sm text-signal-no">{err}</p>}

      <button
        onClick={onSubmit}
        disabled={submitting || !ageOk || !cguOk}
        className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold disabled:opacity-50 hover:bg-brand-400 transition-premium"
      >
        Débloquer le trading réel
      </button>
    </div>
  )
}
