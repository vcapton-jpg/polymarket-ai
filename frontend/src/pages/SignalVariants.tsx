/**
 * Design exploration page — compare 4 signal card variants side by side.
 * Visit /signal-variants to see them. Remove this page once a direction is chosen.
 */

import { MOCK_SIGNALS } from "@/data/signals"
import { SignalCard } from "@/components/signals/SignalCard"
import { SignalCardV1, SignalCardV2, SignalCardV3, SignalCardV4 } from "@/components/signals/SignalCardVariants"

const SIG = MOCK_SIGNALS[3] // Fed/Economy — score 92

const variants = [
  {
    id: "original",
    label: "Original",
    description: "Version actuelle — baseline de comparaison.",
    component: <SignalCard signal={SIG} example />,
  },
  {
    id: "v1",
    label: 'A — "The Brief"',
    description: "Le catalyst mène. Score compact inline. Timer amber quand fenêtre courte. Aucune section redondante.",
    component: <SignalCardV1 signal={SIG} />,
  },
  {
    id: "v2",
    label: 'B — "Score Column"',
    description: "Score en pilier gauche, grande taille. Méta à droite. Catalyst avec icône Zap. Sources avec label « Tier-1 ».",
    component: <SignalCardV2 signal={SIG} />,
  },
  {
    id: "v3",
    label: 'C — "Edge"',
    description: "Densité maximale, zéro chrome superflu. Tout tient en 4 lignes. Sources comme chips. Pour les utilisateurs qui scannent vite.",
    component: <SignalCardV3 signal={SIG} />,
  },
  {
    id: "v4",
    label: 'D — "Conviction Banner"',
    description: "Couleur contextuelle selon le score (brand ≥85, amber ≥55). Le badge remplace le score label. Hiérarchie typographique pure.",
    component: <SignalCardV4 signal={SIG} />,
  },
]

export default function SignalVariants() {
  return (
    <div className="min-h-screen bg-obsidian-900 text-ink">
      <main id="main" className="container-page py-16">
        <div className="mb-12">
          <p className="mb-2 font-mono text-[0.6875rem] uppercase tracking-[0.18em] text-brand-400">
            Design exploration
          </p>
          <h1 className="font-display text-[2rem] font-semibold text-ink">
            Signal card — 4 variantes
          </h1>
          <p className="mt-2 text-ink-muted">
            Même signal (Fed, score 92). Même data. Philosophies différentes.
          </p>
        </div>

        <div className="grid gap-10 md:grid-cols-2 xl:grid-cols-2">
          {variants.map((v) => (
            <div key={v.id} className="flex flex-col gap-3">
              <div>
                <span className="font-mono text-[0.75rem] font-semibold text-brand-400">
                  {v.label}
                </span>
                <p className="mt-0.5 text-[0.8125rem] text-ink-muted">{v.description}</p>
              </div>
              {v.component}
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
