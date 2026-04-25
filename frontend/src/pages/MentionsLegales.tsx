import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"

/**
 * Mentions légales obligatoires pour un éditeur de service en ligne en
 * France (loi pour la confiance dans l'économie numérique, 2004-575).
 *
 * ⚠ Placeholder — valeurs à vérifier avant la mise en production
 *   publique (numéro SIREN, directeur de publication, hébergeur exact).
 */
export default function MentionsLegales() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-2xl space-y-6 px-6 py-16 text-ink-muted">
        <h1 className="text-3xl font-bold text-ink">Mentions légales</h1>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Éditeur</h2>
          <p>Foresight SAS (en cours d'immatriculation)</p>
          <p>Capital social : à définir</p>
          <p>SIREN : à compléter</p>
          <p>Siège social : à compléter, France</p>
          <p>Directeur de la publication : à compléter</p>
          <p>
            Contact :{" "}
            <a href="mailto:contact@foresight.app" className="underline hover:text-ink">
              contact@foresight.app
            </a>
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Hébergeur</h2>
          <p>
            L'infrastructure du Service est hébergée par des prestataires
            cloud établis dans l'Union européenne. La liste et les
            coordonnées exactes sont disponibles sur demande à
            contact@foresight.app.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Propriété intellectuelle</h2>
          <p>
            L'ensemble des contenus (textes, logos, interfaces, signaux et
            analyses) publiés sur le Service sont la propriété de Foresight
            SAS ou de ses partenaires. Toute reproduction ou diffusion sans
            accord écrit préalable est interdite.
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Partenaires</h2>
          <p>
            Les marchés prédictifs référencés proviennent de Polymarket
            (Polymarket Inc.). Foresight n'est ni propriétaire, ni opérateur
            de ces marchés. L'accès à Polymarket depuis certaines
            juridictions peut être restreint — se reporter aux{" "}
            <a href="/cgu" className="underline hover:text-ink">
              CGU
            </a>{" "}
            et à la{" "}
            <a href="/risques" className="underline hover:text-ink">
              politique de risque
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  )
}
