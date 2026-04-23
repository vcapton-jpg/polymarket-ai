import type { SignalOutcome } from "@/types/signal"

type Props = { outcome: SignalOutcome }

/**
 * Post-resolution explainer card shown on `/signals/:id/outcome`.
 * Framed as a learning moment: direction check + price move + one-line
 * lesson (`learningPoint`). Color-graded so the outcome is obvious at
 * a glance without being triumphalist on wins or harsh on losses.
 */
export function OutcomeExplainer({ outcome }: Props) {
  const ok = outcome.directionCorrect === true
  const notOk = outcome.directionCorrect === false
  const tone = ok
    ? "border-signal-yes/40 bg-signal-yes/5"
    : notOk
      ? "border-signal-no/40 bg-signal-no/5"
      : "border-line/60 bg-obsidian-850"
  const headline = ok
    ? "Direction correcte"
    : notOk
      ? "Direction incorrecte"
      : "Résultat indéterminé"
  const icon = ok ? "✓" : notOk ? "✗" : "—"

  return (
    <section
      className={`rounded-xl border p-6 space-y-3 ${tone}`}
      aria-label="Résultat du signal"
    >
      <div className="flex items-center gap-2">
        <span
          className="text-2xl"
          aria-hidden="true"
        >
          {icon}
        </span>
        <h3 className="text-lg font-semibold text-ink">{headline}</h3>
      </div>

      {outcome.basePrice !== null && outcome.finalPrice !== null && (
        <p className="text-sm text-ink-muted">
          {`Prix au signal : `}
          <strong className="num text-ink">
            {`${Math.round(outcome.basePrice * 100)}%`}
          </strong>
          {` → résolution : `}
          <strong className="num text-ink">
            {`${Math.round(outcome.finalPrice * 100)}%`}
          </strong>
          {outcome.movePct !== null && (
            <>
              {` (mouvement : `}
              <strong className="num text-ink">
                {`${outcome.movePct > 0 ? "+" : ""}${outcome.movePct.toFixed(1)}%`}
              </strong>
              {`)`}
            </>
          )}
        </p>
      )}

      <p className="text-sm leading-relaxed text-ink">{outcome.learningPoint}</p>
    </section>
  )
}
