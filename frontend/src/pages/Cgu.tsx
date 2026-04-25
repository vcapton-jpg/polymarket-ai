import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"

/**
 * Conditions Générales d'Utilisation (`/cgu`).
 *
 * ⚠ Placeholder — à valider par un avocat fintech FR avant la mise en
 *   production publique. Les clauses ci-dessous posent le cadre minimum
 *   (objet, responsabilité, résiliation) mais ne remplacent pas un
 *   audit légal.
 */
export default function Cgu() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-2xl space-y-6 px-6 py-16 text-ink-muted">
        <h1 className="text-3xl font-bold text-ink">Conditions Générales d'Utilisation</h1>
        <p className="text-sm text-ink-dim">Dernière mise à jour : 23 avril 2026</p>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">1. Objet</h2>
          <p>
            Foresight (ci-après « le Service ») est une plateforme éducative
            qui détecte et explique des signaux à partir de marchés
            prédictifs publics (Polymarket). Le Service ne constitue pas un
            conseil en investissement et n'agit pas en tant que prestataire
            de services d'investissement au sens du Code monétaire et
            financier français.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">2. Accès et inscription</h2>
          <p>
            L'utilisation du Service est réservée aux personnes majeures (18
            ans révolus) résidant dans une juridiction où l'accès aux
            marchés prédictifs est autorisé. L'utilisateur est seul
            responsable de la vérification de cette légalité.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">3. Paper trading et trading réel</h2>
          <p>
            Le Service propose un mode paper trading (simulation sans
            argent réel) et, après validation du tutoriel, du quiz risque et
            des limites, un mode trading réel via l'intégration Polymarket.
            Les limites (budget hebdomadaire, mise max, pause après pertes
            consécutives) sont appliquées côté serveur et non
            contournables.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">4. Responsabilité</h2>
          <p>
            L'utilisateur reste seul décisionnaire et seul responsable de
            ses ordres. Foresight ne garantit ni la performance passée ni
            la performance future des signaux diffusés. Se reporter à la{" "}
            <a href="/risques" className="underline hover:text-ink">
              politique de risque
            </a>
            .
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">5. Résiliation</h2>
          <p>
            L'utilisateur peut résilier son compte à tout moment depuis
            l'écran Paramètres. Foresight peut suspendre un compte en cas
            de manquement grave aux présentes CGU.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-xl font-semibold text-ink">6. Données personnelles</h2>
          <p>
            Les données collectées (email, activité, limites) sont traitées
            conformément au RGPD. L'utilisateur dispose des droits d'accès,
            de rectification et de suppression en écrivant à
            contact@foresight.app.
          </p>
        </section>
      </main>
      <Footer />
    </div>
  )
}
