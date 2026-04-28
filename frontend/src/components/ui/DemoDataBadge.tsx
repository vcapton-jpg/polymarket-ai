import { AlertTriangle } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Persistent label rendered atop any surface that's currently
 * displaying mock / demo data — Performance.tsx and Portfolio.tsx
 * fall back to the `MOCK_PERFORMANCE` bundle when the API is
 * unreachable or the user is not logged in.
 *
 * Legal-PR-3 audit finding B8 + M10: showing fabricated KPIs without
 * an explicit "demo" label is the AMF's first-strike target on
 * promotional communications. This badge is the single source of
 * truth for that disclosure — every page that can render mocks must
 * mount it conditionally.
 *
 * Visual contract: brand-amber, never close to invisible. The badge
 * sits in the page-content scroll context (not pinned) so the user
 * sees it on first paint and again whenever they scroll back up.
 */
export function DemoDataBadge({
  className,
  reason = "default",
}: {
  className?: string
  /** Optional sub-label hint when the cause is known (no auth, API
   *  down, etc.) — kept short, not a full diagnosis. */
  reason?: "default" | "no-auth" | "api-error"
}) {
  const sublabel: Record<typeof reason, string> = {
    default: "Les chiffres affichés ne sont pas issus de ton activité réelle.",
    "no-auth":
      "Connecte-toi pour voir tes propres chiffres ; en attendant, ce sont des données de démonstration.",
    "api-error":
      "L’API est momentanément indisponible — affichage en démonstration.",
  }
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn(
        "flex items-start gap-2.5 rounded-lg border border-signal-amber/40 bg-signal-amber/[0.08] px-4 py-3",
        className,
      )}
    >
      <AlertTriangle
        className="mt-0.5 h-4 w-4 shrink-0 text-signal-amber"
        aria-hidden
      />
      <div className="min-w-0 text-body-sm">
        <p className="font-semibold text-signal-amber">
          Données de démonstration
        </p>
        <p className="mt-0.5 leading-relaxed text-ink-muted">
          {sublabel[reason]}
        </p>
      </div>
    </div>
  )
}
