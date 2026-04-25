/**
 * Defensive React error boundary.
 *
 * Used in two layers:
 *   1. **Root** (mounted in `main.tsx` around `<App/>`) — last-resort
 *      catch so a thrown render stays inside a styled fallback rather
 *      than producing a fully blank page.
 *   2. **Per-route** (mounted by `App.tsx` around each lazy `<Route>`
 *      element) — keeps the rest of the shell (header, nav) intact when
 *      a single page errors. The shell itself is outside the per-route
 *      boundaries so navigation still works.
 *
 * The fallback intentionally avoids any app-level providers (no router
 * navigation, no toast hook): a child that has just crashed cannot be
 * trusted to have working context. The "Recharger" CTA does a hard
 * `location.reload()` because that is the only universally safe escape
 * hatch when component state is in an unknown shape.
 *
 * In production we hand the error to `console.error` only — wire to
 * Sentry / your error tracker in `componentDidCatch` when ready.
 */
import { Component, type ErrorInfo, type ReactNode } from "react"
import { AlertTriangle, RotateCcw } from "lucide-react"

type Props = {
  children: ReactNode
  /** Hint shown above the message — e.g. "Page Signaux", "Bandeau global". */
  scope?: string
  /** Optional render-prop fallback. Receives the error and a reset fn that
   *  attempts an in-place recovery (clears the error state). Reset only
   *  works if the error was transient (network blip, aborted promise);
   *  for bad render logic the error will recur immediately. */
  fallback?: (args: { error: Error; reset: () => void }) => ReactNode
}

type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error(
      `[ErrorBoundary${this.props.scope ? ` · ${this.props.scope}` : ""}]`,
      error,
      info.componentStack,
    )
  }

  reset = () => this.setState({ error: null })

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    if (this.props.fallback) {
      return this.props.fallback({ error, reset: this.reset })
    }

    return (
      <div
        role="alert"
        aria-live="assertive"
        className="mx-auto my-12 flex max-w-md flex-col items-center gap-4 rounded-2xl border border-signal-no/30 bg-obsidian-850/80 px-6 py-8 text-center"
      >
        <span className="grid h-10 w-10 place-items-center rounded-full bg-signal-no/15 text-signal-no ring-1 ring-signal-no/30">
          <AlertTriangle className="h-5 w-5" aria-hidden />
        </span>
        {this.props.scope && (
          <p className="font-mono text-label-xs uppercase tracking-[0.14em] text-ink-dim">
            {this.props.scope}
          </p>
        )}
        <h2 className="font-display text-title-sm font-semibold text-ink">
          {"Quelque chose s\u2019est cass\u00e9"}
        </h2>
        <p className="text-body-sm text-ink-muted">
          {"On a remont\u00e9 l\u2019erreur. Recharge la page pour repartir d\u2019un \u00e9tat propre."}
        </p>
        <details className="w-full text-left">
          <summary className="cursor-pointer text-label-sm text-ink-dim hover:text-ink-muted">
            {"D\u00e9tails techniques"}
          </summary>
          <pre className="mt-2 max-h-40 overflow-auto rounded-md border border-line/60 bg-obsidian-900 p-2 text-label-xs text-ink-muted">
            {error.message}
          </pre>
        </details>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={this.reset}
            className="inline-flex items-center gap-1.5 rounded-md border border-line-strong bg-obsidian-800 px-3 py-2 text-body-sm text-ink-muted transition-premium hover:border-brand-500/40 hover:text-ink"
          >
            {"R\u00e9essayer"}
          </button>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-1.5 rounded-md bg-brand-500 px-3 py-2 text-body-sm font-semibold text-obsidian-950 transition-premium hover:bg-brand-400"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden />
            Recharger
          </button>
        </div>
      </div>
    )
  }
}
