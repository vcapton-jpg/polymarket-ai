import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { fetchQuizQuestions, submitQuiz } from "@/lib/api/onboarding"

/**
 * Risk-acknowledgment quiz — mandatory 3/3 gate for real trading.
 *
 * Failing the quiz inserts a `QuizAttempt` row on the backend but leaves
 * `UserLimits.quiz_passed=False` and `OnboardingProgress.quiz_done=False`.
 * The user can retry as many times as they want. Passing (3/3) flips
 * both flags and auto-forwards to /welcome/budget after 1.5s.
 */
export default function Quiz() {
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<{ score: number; passed: boolean } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  const { data: questions = [] } = useQuery({
    queryKey: ["quiz-questions"],
    queryFn: fetchQuizQuestions,
  })

  async function onSubmit() {
    if (submitting) return
    setSubmitting(true)
    setError(null)
    try {
      const r = await submitQuiz(answers)
      setResult({ score: r.score, passed: r.passed })
      if (r.passed) {
        setTimeout(() => navigate("/welcome/budget"), 1500)
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de valider le quiz — réessaie.")
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered =
    questions.length > 0 && questions.every((q) => q.id in answers)

  return (
    <div className="mx-auto max-w-2xl p-6 space-y-6">
      <h1 className="text-2xl font-bold">Quiz risque — 3 questions</h1>
      <p className="text-sm text-ink-muted">
        Il faut 3/3 pour débloquer le trading réel. Tu peux recommencer si tu échoues.
      </p>

      {questions.map((q, qi) => (
        <div
          key={q.id}
          className="rounded-xl border border-line-strong bg-obsidian-850/60 p-4 space-y-3"
        >
          <p className="font-semibold">{`${qi + 1}. ${q.question}`}</p>
          <div className="flex flex-col gap-2">
            {q.choices.map((c, ci) => (
              <label
                key={ci}
                className="flex items-center gap-2 cursor-pointer"
              >
                <input
                  type="radio"
                  name={q.id}
                  checked={answers[q.id] === ci}
                  onChange={() => setAnswers({ ...answers, [q.id]: ci })}
                  disabled={result?.passed === true}
                />
                <span className="text-sm">{c}</span>
              </label>
            ))}
          </div>
        </div>
      ))}

      {error && (
        <div className="rounded-lg border border-signal-no/40 bg-signal-no/10 p-3 text-sm">
          {error}
        </div>
      )}

      <button
        onClick={onSubmit}
        disabled={!allAnswered || submitting || result?.passed === true}
        className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold disabled:opacity-50 hover:bg-brand-400 transition-premium"
      >
        Valider
      </button>

      {result && (
        <div
          className={`rounded-lg p-4 ${
            result.passed ? "bg-signal-yes/10" : "bg-signal-no/10"
          }`}
        >
          <p className="font-semibold">
            {result.passed
              ? `✓ Bravo, ${result.score}/3. Tu débloques le trading réel.`
              : `✗ ${result.score}/3. Relis les questions et retente.`}
          </p>
          {!result.passed && (
            <button
              onClick={() => {
                setResult(null)
                setAnswers({})
              }}
              className="mt-3 text-sm underline"
            >
              Recommencer
            </button>
          )}
        </div>
      )}
    </div>
  )
}
