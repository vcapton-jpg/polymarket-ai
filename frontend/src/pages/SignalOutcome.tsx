import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { apiPost } from "@/lib/api/client"
import { fetchSignalDetailFromApi } from "@/lib/apiSignals"
import { OutcomeExplainer } from "@/components/learn/OutcomeExplainer"
import { WhyThisMatters } from "@/components/signals/WhyThisMatters"
import { SourcesList } from "@/components/signals/SourcesList"
import { Skeleton } from "@/components/ui/Skeleton"

/**
 * Post-resolution learning page for a signal (`/signals/:id/outcome`).
 *
 * Shows the `SignalOutcome` explainer + the same reasoning/sources block
 * as the detail page so the user can compare their original call to
 * what actually happened. Pings `/signals/:id/outcome/viewed` once when
 * the outcome is present (fire-and-forget; powers Task 19 gamification).
 *
 * Unresolved signals fall through to a gentle "come back later" state
 * instead of 404ing.
 */
export default function SignalOutcome() {
  const { id = "" } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const { data: signal, isLoading } = useQuery({
    queryKey: ["signal-detail", id],
    queryFn: () => fetchSignalDetailFromApi(id),
    enabled: id.length > 0,
  })

  useEffect(() => {
    if (!id || !signal?.outcome) return
    // Fire-and-forget: analytics + gamification hook. Failures are silent —
    // the user has already seen the card.
    void apiPost(`/signals/${id}/outcome/viewed`, {}).catch(() => undefined)
  }, [id, signal?.outcome])

  if (isLoading || !signal) {
    return (
      <main id="main" className="mx-auto max-w-3xl space-y-4 p-6">
        <Skeleton className="h-7 w-3/4" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-5/6" />
        <Skeleton className="h-48 w-full" />
        <Skeleton className="h-32 w-full" />
      </main>
    )
  }

  if (!signal.outcome) {
    return (
      <main id="main" className="mx-auto max-w-2xl space-y-4 p-6">
        <h1 className="text-2xl font-bold text-ink">{signal.question}</h1>
        <p className="text-sm text-ink-muted">
          Ce signal n'est pas encore résolu. Reviens quand le marché aura
          tranché — on te montrera ce qui s'est passé et pourquoi.
        </p>
        <button
          type="button"
          onClick={() => navigate(`/signals/${id}`)}
          className="text-sm text-brand-400 underline hover:text-brand-300"
        >
          Retour au signal
        </button>
      </main>
    )
  }

  return (
    <main id="main" className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-bold text-ink">{signal.question}</h1>
      <OutcomeExplainer outcome={signal.outcome} />
      <WhyThisMatters
        reasoning={signal.reasoning ?? null}
        sourceTierMix={signal.sourceTierMix ?? null}
      />
      {signal.detailedSources && signal.detailedSources.length > 0 && (
        <SourcesList sources={signal.detailedSources} />
      )}
      <button
        type="button"
        onClick={() => navigate("/signals")}
        className="w-full rounded-lg bg-brand-500 py-3 font-semibold text-obsidian-950 transition-premium hover:bg-brand-400"
      >
        Compris, voir d'autres signaux
      </button>
    </main>
  )
}
