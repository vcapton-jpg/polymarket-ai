import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"

/**
 * Public risk-policy page (`/risques`). Framed as a plain-language
 * explainer + a pointer to support resources. Must be linked from the
 * footer, signup checkboxes, and the budget-setup page.
 *
 * ⚠ Placeholder text — validate with a French fintech lawyer before
 *   public launch.
 */
export default function Risques() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-2xl space-y-6 px-6 py-16">
        <h1 className="text-3xl font-bold">Politique de risque</h1>
        <p className="text-ink-muted">
          Les marchés prédictifs (Polymarket et équivalents) sont un produit à
          haut risque. Tu peux perdre la totalité de la mise que tu engages.
          Avant tout trade réel :
        </p>
        <ul className="list-disc space-y-2 pl-6 text-ink-muted">
          <li>Ne trade jamais plus que ce que tu peux te permettre de perdre.</li>
          <li>
            Les signaux sont une analyse d'intérêt éducative, pas une
            recommandation d'investissement.
          </li>
          <li>
            Le passé ne garantit pas l'avenir. Un winrate historique peut
            s'inverser.
          </li>
          <li>Tu restes seul responsable de tes décisions d'investissement.</li>
          <li>
            Si tu te sens dépassé, prends une pause et contacte Joueurs Info
            Service au 09 74 75 13 13 (appel non-surtaxé, anonyme et gratuit).
          </li>
        </ul>
        <section className="rounded-xl border border-signal-no/30 bg-signal-no/5 p-4 text-sm text-ink">
          <h2 className="mb-2 font-semibold">Protections automatiques</h2>
          <ul className="list-disc space-y-1 pl-5 text-ink-muted">
            <li>
              Budget hebdomadaire et mise max plafonnés côté serveur — aucun
              ordre réel n'est passé au-delà de tes limites.
            </li>
            <li>
              Pause forcée de 24h après 3 pertes consécutives (cooloff), pour
              casser le tilt.
            </li>
            <li>Confirmation 18+ et quiz risque obligatoires avant le premier trade réel.</li>
          </ul>
        </section>
        <p className="text-sm text-ink-dim">
          Ce site ne fournit pas de conseil en investissement au sens de
          l'AMF. L'accès à Polymarket peut être restreint dans certaines
          juridictions ; tu es responsable de vérifier la légalité d'usage
          dans ton pays de résidence.
        </p>
      </main>
      <Footer />
    </div>
  )
}
