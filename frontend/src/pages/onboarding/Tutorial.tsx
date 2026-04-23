import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { TUTORIAL_SCENARIOS } from "@/content/tutorialScenarios"
import { openPaperTrade } from "@/lib/api/paper"

/**
 * 5-scenario tutorial page. Each scenario is a paper trade (5€ virtual,
 * `is_tutorial=true`) — the backend counts these and flips
 * `onboarding_progress.tutorial_done` after the 5th trade. The feedback
 * block after each choice shows whether the user read the scenario the
 * "right" way, using `correctDirection` from the hardcoded scenario data.
 *
 * On completion → /welcome/quiz.
 */
export default function Tutorial() {
  const [idx, setIdx] = useState(0)
  const [lastResult, setLastResult] = useState<"correct" | "incorrect" | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const scenario = TUTORIAL_SCENARIOS[idx]

  async function choose(direction: "YES" | "NO") {
    if (submitting || !scenario) return
    setSubmitting(true)
    setError(null)
    try {
      await openPaperTrade({
        marketId: scenario.marketId,
        direction,
        stakeEur: 5,
        entryPrice: scenario.entryPrice,
        isTutorial: true,
      })
      setLastResult(direction === scenario.correctDirection ? "correct" : "incorrect")
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible d'enregistrer ton choix — réessaie.")
    } finally {
      setSubmitting(false)
    }
  }

  function next() {
    setLastResult(null)
    if (idx + 1 >= TUTORIAL_SCENARIOS.length) {
      navigate("/welcome/quiz")
    } else {
      setIdx(idx + 1)
    }
  }

  if (!scenario) return null

  return (
    <div className="mx-auto max-w-2xl p-6 space-y-6">
      <h1 className="text-2xl font-bold">
        Tutoriel — scénario {idx + 1} / {TUTORIAL_SCENARIOS.length}
      </h1>
      <div className="rounded-xl border border-line-strong bg-obsidian-850/60 p-6 space-y-3">
        <p className="text-xs uppercase text-ink-dim">{scenario.category}</p>
        <h2 className="text-lg font-semibold">{scenario.question}</h2>
        <p className="text-sm">Prix actuel YES : {(scenario.entryPrice * 100).toFixed(0)}%</p>
        <p className="text-sm text-ink-muted">{scenario.narrative}</p>
      </div>

      {error && (
        <div className="rounded-lg border border-signal-no/40 bg-signal-no/10 p-3 text-sm">
          {error}
        </div>
      )}

      {lastResult === null ? (
        <div className="flex gap-3">
          <button
            onClick={() => choose("YES")}
            disabled={submitting}
            className="flex-1 rounded-lg bg-signal-yes/20 hover:bg-signal-yes/30 disabled:opacity-50 py-3 font-semibold transition-premium"
          >
            Parier YES (5€ virtuels)
          </button>
          <button
            onClick={() => choose("NO")}
            disabled={submitting}
            className="flex-1 rounded-lg bg-signal-no/20 hover:bg-signal-no/30 disabled:opacity-50 py-3 font-semibold transition-premium"
          >
            Parier NO (5€ virtuels)
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div
            className={`rounded-lg p-4 ${
              lastResult === "correct" ? "bg-signal-yes/10" : "bg-signal-no/10"
            }`}
          >
            <p className="font-semibold">
              {lastResult === "correct" ? "✓ Bonne lecture" : "✗ Leçon à retenir"}
            </p>
            <p className="text-sm mt-2">{scenario.explanation}</p>
          </div>
          <button
            onClick={next}
            className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold hover:bg-brand-400 transition-premium"
          >
            {idx + 1 >= TUTORIAL_SCENARIOS.length ? "Passer au quiz →" : "Scénario suivant →"}
          </button>
        </div>
      )}
    </div>
  )
}
