import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"
import { LEGAL } from "@/lib/legal"

/**
 * Conditions Générales de Vente (`/cgv`).
 *
 * Code de la consommation L221-5 (information précontractuelle) +
 * L221-18 (droit de rétractation 14 jours sur les services) +
 * L221-25 (renoncement express au droit de rétractation pour les
 * services numériques exécutés immédiatement).
 *
 * Cible : abonnement Pro mensuel. Le tarif TTC, le caractère récurrent
 * du paiement, le droit de rétractation et la procédure de réclamation
 * sont tous obligatoires.
 *
 * ⚠ Draft template — à valider par un avocat fintech FR avant la mise
 * en production publique. Les montants et le mode de paiement sont
 * cependant alignés sur le code (cf. Pricing.tsx + Stripe Checkout).
 */
export default function Cgv() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-3xl space-y-8 px-6 py-16 text-ink-muted">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold text-ink">Conditions Générales de Vente</h1>
          <p className="text-sm text-ink-dim">
            Dernière mise à jour : 28 avril 2026 · Version 1
          </p>
        </header>

        <Block title="1. Identification du vendeur">
          <p>
            Les présentes CGV sont conclues entre <strong>{LEGAL.company.name}</strong>{" "}
            (ci-après « le Vendeur »), dont les coordonnées complètes
            figurent dans les{" "}
            <a href="/mentions-legales" className="underline hover:text-ink">
              mentions légales
            </a>
            , et tout utilisateur souscrivant à l'offre Pro (ci-après «
            le Client »).
          </p>
        </Block>

        <Block title="2. Objet">
          <p>
            Le Vendeur propose un service d'analyse de marchés
            prédictifs sous forme d'abonnement (« Foresight Pro »). Les
            CGV régissent toute souscription, modification, et
            résiliation du dit abonnement.
          </p>
          <p>
            La souscription d'un abonnement Pro emporte adhésion sans
            réserve aux présentes CGV ainsi qu'aux{" "}
            <a href="/cgu" className="underline hover:text-ink">
              CGU
            </a>{" "}
            et à la{" "}
            <a href="/confidentialite" className="underline hover:text-ink">
              politique de confidentialité
            </a>
            .
          </p>
        </Block>

        <Block title="3. Tarifs et modalités de paiement">
          <Table
            head={["Offre", "Tarif TTC", "Engagement", "Essai gratuit"]}
            rows={[
              ["Pro mensuel", "29,00 € / mois (TVA 20 % incluse)", "Sans engagement, résiliable à tout moment", "7 jours sans carte"],
            ]}
          />
          <p>
            Le paiement est traité par Stripe Payments Europe Ltd.
            (Irlande). Le Client garantit disposer des autorisations
            nécessaires sur le moyen de paiement utilisé.
          </p>
          <p>
            <strong>Renouvellement :</strong> l'abonnement se reconduit
            tacitement à la fin de chaque période de facturation pour
            une durée identique. Le Client peut le résilier à tout
            moment depuis Paramètres → « Gérer mon abonnement » (portail
            Stripe), ce qui prend effet à la fin de la période en cours.
          </p>
          <p>
            <strong>Échec de paiement :</strong> en cas de prélèvement
            refusé, l'accès aux fonctionnalités Pro est suspendu jusqu'à
            régularisation. Trois échecs successifs entraînent la
            bascule automatique vers l'offre gratuite.
          </p>
        </Block>

        <Block title="4. Droit de rétractation (L221-18 du Code de la consommation)">
          <p>
            Conformément à l'article L221-18, le Client dispose d'un
            délai de <strong>14 jours</strong> à compter de la date de
            souscription pour exercer son droit de rétractation, sans
            avoir à motiver sa décision. La demande doit être adressée
            par courriel à{" "}
            <a
              href={`mailto:${LEGAL.contact.general}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.general}
            </a>
            ou via le portail de gestion d'abonnement.
          </p>
          <p>
            <strong>Effet :</strong> remboursement intégral des sommes
            versées dans un délai maximal de 14 jours suivant
            l'exercice du droit, par le même moyen de paiement que celui
            utilisé pour la transaction initiale.
          </p>
          <p className="rounded-lg border border-signal-amber/30 bg-signal-amber/[0.06] px-4 py-3">
            <strong className="text-ink">
              Renoncement exprès au droit de rétractation (L221-25) —
            </strong>{" "}
            le Client reconnaît que l'accès aux signaux et fonctionnalités
            Pro constitue un service numérique fourni{" "}
            <strong>immédiatement</strong> dès la souscription. En cochant
            la case dédiée lors du paiement, le Client demande
            expressément l'exécution immédiate du service{" "}
            <strong>et accepte la perte de son droit de rétractation</strong>
            une fois le service pleinement exécuté. Si le Client ne
            renonce pas, l'accès aux signaux Pro reste différé de 14
            jours.
          </p>
        </Block>

        <Block title="5. Garanties et responsabilité">
          <p>
            Le Service est fourni « en l'état » et constitue une aide à
            la décision. Foresight ne garantit ni la performance passée
            ni la performance future des signaux diffusés. Le Client
            reste seul décisionnaire et seul responsable de ses ordres,
            comme rappelé dans la{" "}
            <a href="/risques" className="underline hover:text-ink">
              politique de risque
            </a>
            .
          </p>
          <p>
            Le Vendeur ne saurait être tenu pour responsable des pertes
            financières liées à la prise de position sur les marchés
            prédictifs Polymarket, ni des éventuelles indisponibilités
            techniques de Polymarket lui-même.
          </p>
        </Block>

        <Block title="6. Réclamation et médiation">
          <p>
            Toute réclamation peut être adressée par courriel à{" "}
            <a
              href={`mailto:${LEGAL.contact.general}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.general}
            </a>
            . Le Vendeur s'engage à apporter une première réponse sous
            10 jours ouvrés.
          </p>
          <p>
            En cas de désaccord persistant, le Client peut saisir
            gratuitement le médiateur de la consommation compétent
            (article L612-1 du Code de la consommation). Les
            coordonnées du médiateur seront publiées sur cette page
            avant la première souscription payante.
          </p>
        </Block>

        <Block title="7. Données personnelles">
          <p>
            Le traitement des données dans le cadre de l'exécution du
            contrat est décrit dans la{" "}
            <a href="/confidentialite" className="underline hover:text-ink">
              politique de confidentialité
            </a>
            . Les données de paiement sont traitées exclusivement par
            Stripe ; le Vendeur ne stocke aucune coordonnée bancaire.
          </p>
        </Block>

        <Block title="8. Loi applicable et juridiction compétente">
          <p>
            Les présentes CGV sont soumises au droit français. À défaut
            de résolution amiable, tout litige sera porté devant les
            tribunaux français compétents, sous réserve des dispositions
            d'ordre public protectrices du consommateur.
          </p>
        </Block>
      </main>
      <Footer />
    </div>
  )
}

function Block({
  title,
  children,
}: {
  title: string
  children: React.ReactNode
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold text-ink">{title}</h2>
      {children}
    </section>
  )
}

function Table({ head, rows }: { head: string[]; rows: string[][] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line/60">
      <table className="w-full text-left text-body-sm">
        <thead className="bg-obsidian-850/60">
          <tr>
            {head.map((h) => (
              <th
                key={h}
                scope="col"
                className="px-3 py-2 font-mono text-label-xs uppercase tracking-[0.12em] text-ink-dim"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-line/60">
          {rows.map((r, i) => (
            <tr key={i} className="align-top">
              {r.map((cell, j) => (
                <td key={j} className="px-3 py-2 text-ink-muted">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
