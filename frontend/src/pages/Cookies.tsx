import { useState } from "react"
import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"
import { Button } from "@/components/ui/Button"
import { revoke as revokeConsent, useConsent } from "@/lib/cookieConsent"

/**
 * Politique cookies (`/cookies`).
 *
 * Décrit l'inventaire réel du stockage local + les futurs trackers
 * sous-tendus par le bandeau de consentement. Permet aussi de revoir
 * son choix en un clic — la conformité CNIL exige cet accès direct.
 */
export default function Cookies() {
  const consent = useConsent()
  const [confirmation, setConfirmation] = useState<string | null>(null)

  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-3xl space-y-8 px-6 py-16 text-ink-muted">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold text-ink">
            Politique de gestion des cookies
          </h1>
          <p className="text-sm text-ink-dim">
            Dernière mise à jour : 28 avril 2026 · Version 1
          </p>
        </header>

        <Block title="1. Ce qu'on appelle « cookie » ici">
          <p>
            Foresight n'utilise <strong>pas</strong> de cookies HTTP au
            sens strict. Le Service stocke en revanche quelques
            informations dans le <em>localStorage</em> de ton navigateur,
            soumises au même cadre légal (CNIL délibération 2020-091).
            Cette page liste tous les éléments stockés et précise
            lesquels sont nécessaires au fonctionnement et lesquels
            requièrent ton consentement.
          </p>
        </Block>

        <Block title="2. Catégorie « Indispensable » — sans consentement (Art. 82 al. 2)">
          <p>
            Ces clés sont strictement nécessaires à la fourniture du
            Service tel que demandé. Leur dépôt ne peut techniquement
            pas être différé sans casser l'expérience.
          </p>
          <Table
            head={["Clé", "Contenu", "Durée"]}
            rows={[
              ["foresight.token", "Jeton de session JWT", "7 jours (expiration serveur)"],
              ["foresight.auth", "Email + plan + date de fin d'essai", "Session locale"],
              ["foresight.profile", "Profil de trading sélectionné", "Session locale"],
              ["foresight.positions", "Positions actuellement ouvertes", "Tant qu'une position est ouverte"],
              ["foresight.settings", "Préférences notifications, devise, langue", "Session locale"],
              ["foresight.onboarding", "État d'onboarding de l'utilisateur", "Jusqu'à la complétion"],
              ["foresight.cookieConsent", "Trace de ton choix de cookies (cf. § 5)", "Indéfini, révocable"],
            ]}
          />
        </Block>

        <Block title="3. Catégorie « Mesure d'audience » — soumise à consentement">
          <p>
            Mesures anonymes et agrégées (nombre de pages vues, signaux
            consultés, performances de l'API). Aucun outil de mesure
            n'est aujourd'hui en place ; cette catégorie est réservée
            pour qu'aucun futur outil ne puisse être ajouté sans
            recueillir d'abord ton accord explicite.
          </p>
        </Block>

        <Block title="4. Catégorie « Marketing » — soumise à consentement">
          <p>
            Pixels publicitaires, audiences personnalisées, conversion
            cross-site. Aucun script de cette catégorie n'est utilisé
            aujourd'hui. La catégorie reste verrouillée par le bandeau
            de consentement par défaut.
          </p>
        </Block>

        <Block title="5. Tes choix actuels">
          {consent ? (
            <>
              <p>
                Décision enregistrée le{" "}
                <strong>
                  {new Date(consent.decidedAt).toLocaleString("fr-FR", {
                    dateStyle: "long",
                    timeStyle: "short",
                  })}
                </strong>{" "}
                :
              </p>
              <ul className="list-inside list-disc space-y-1">
                <li>
                  Indispensable :{" "}
                  <strong className="text-signal-yes">activé</strong>{" "}
                  (toujours)
                </li>
                <li>
                  Mesure d'audience :{" "}
                  <strong
                    className={
                      consent.categories.analytics
                        ? "text-signal-yes"
                        : "text-ink-dim"
                    }
                  >
                    {consent.categories.analytics ? "activé" : "refusé"}
                  </strong>
                </li>
                <li>
                  Marketing :{" "}
                  <strong
                    className={
                      consent.categories.marketing
                        ? "text-signal-yes"
                        : "text-ink-dim"
                    }
                  >
                    {consent.categories.marketing ? "activé" : "refusé"}
                  </strong>
                </li>
              </ul>
            </>
          ) : (
            <p>
              Aucun choix enregistré pour le moment. Le bandeau de
              consentement s'affichera lors de ta prochaine visite.
            </p>
          )}
        </Block>

        <Block title="6. Modifier ou retirer ton consentement">
          <p>
            Cliquer ci-dessous efface ton choix actuel. Le bandeau de
            consentement s'affichera de nouveau pour te permettre de
            revoir tes préférences en un clic.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Button
              variant="outline"
              size="md"
              onClick={() => {
                revokeConsent()
                setConfirmation(
                  "Choix effacé. Le bandeau s'affichera lors de la prochaine action sur le site.",
                )
              }}
            >
              Revoir mes choix de cookies
            </Button>
            {confirmation && (
              <span className="text-label-sm text-brand-300">{confirmation}</span>
            )}
          </div>
        </Block>

        <Block title="7. Réclamation">
          <p>
            En cas de difficulté liée aux cookies, tu peux nous écrire
            (cf.{" "}
            <a href="/mentions-legales" className="underline hover:text-ink">
              mentions légales
            </a>
            ) ou saisir la CNIL (
            <a
              href="https://www.cnil.fr/fr/plaintes"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-ink"
            >
              cnil.fr/fr/plaintes
            </a>
            ).
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
