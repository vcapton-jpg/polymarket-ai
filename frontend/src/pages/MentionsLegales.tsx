import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"
import { LEGAL, isLegalConfigured, legalSlot } from "@/lib/legal"

/**
 * Mentions légales obligatoires pour un éditeur de service en ligne en
 * France (loi 2004-575 art. 6.III, dite « LCEN »). Doivent identifier :
 *   - l'éditeur (raison sociale, capital, RCS, siège, dir. publication)
 *   - l'hébergeur (nom, adresse, téléphone)
 *   - les modalités de contact
 *
 * Les valeurs ci-dessous proviennent de `lib/legal.ts`, alimenté par les
 * variables d'environnement VITE_LEGAL_*. Tant qu'une variable n'est pas
 * fixée, son emplacement affiche le marqueur visible
 * "[À compléter avant production]" — un signal volontairement bruyant
 * pour bloquer une mise en ligne accidentelle avec des stubs.
 */
export default function MentionsLegales() {
  const configured = isLegalConfigured()

  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-2xl space-y-6 px-6 py-16 text-ink-muted">
        <h1 className="text-3xl font-bold text-ink">Mentions légales</h1>

        {!configured && (
          <div
            role="alert"
            className="rounded-lg border border-signal-amber/40 bg-signal-amber/10 px-4 py-3 text-body-sm text-signal-amber"
          >
            ⚠ Cette page contient des emplacements non encore renseignés
            (variables <code className="font-mono">VITE_LEGAL_*</code>). À
            compléter par l'opérateur avant toute mise en production publique.
          </div>
        )}

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Éditeur</h2>
          <p>{LEGAL.company.name}</p>
          <p>Capital social : {legalSlot(LEGAL.company.capital)}</p>
          <p>SIREN : {legalSlot(LEGAL.company.siren)}</p>
          <p>Siège social : {legalSlot(LEGAL.company.address)}</p>
          <p>Directeur de la publication : {legalSlot(LEGAL.company.pubDirector)}</p>
          <p>
            Contact :{" "}
            <a
              href={`mailto:${LEGAL.contact.general}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.general}
            </a>
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Hébergeur</h2>
          <p>{legalSlot(LEGAL.hosting.name)}</p>
          <p>{legalSlot(LEGAL.hosting.address)}</p>
          <p>Téléphone : {legalSlot(LEGAL.hosting.phone)}</p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Délégué à la protection des données (DPO)</h2>
          <p>
            Pour toute question relative au traitement de tes données :{" "}
            <a
              href={`mailto:${LEGAL.contact.dpo}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.dpo}
            </a>
            . Tu peux également exercer tes droits depuis l'onglet
            « Paramètres » du Service ou auprès de la CNIL (
            <a
              href="https://www.cnil.fr"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-ink"
            >
              www.cnil.fr
            </a>
            ).
          </p>
        </section>

        <section className="space-y-2">
          <h2 className="text-xl font-semibold text-ink">Propriété intellectuelle</h2>
          <p>
            L'ensemble des contenus (textes, logos, interfaces, signaux et
            analyses) publiés sur le Service sont la propriété de{" "}
            {LEGAL.company.name} ou de ses partenaires. Toute reproduction
            ou diffusion sans accord écrit préalable est interdite.
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
            </a>
            , à la{" "}
            <a href="/risques" className="underline hover:text-ink">
              politique de risque
            </a>{" "}
            et à la{" "}
            <a href="/confidentialite" className="underline hover:text-ink">
              politique de confidentialité
            </a>
            .
          </p>
        </section>
      </main>
      <Footer />
    </div>
  )
}
