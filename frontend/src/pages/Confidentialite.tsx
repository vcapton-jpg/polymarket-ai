import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"
import { LEGAL } from "@/lib/legal"

/**
 * Politique de confidentialité (`/confidentialite`).
 *
 * Cible : RGPD art. 13/14 (transparence) + ePrivacy/CNIL pour le
 * stockage local. Les catégories ci-dessous reflètent l'inventaire
 * réel de la codebase :
 *   - localStorage   (foresight.token, .auth, .profile, .positions,
 *                     .settings, .onboarding, .signup_draft_email,
 *                     .cookieConsent)
 *   - backend        (UserProfile, UserLimits, Signal, Position…)
 *   - tiers          (Polymarket, Stripe, Google OAuth, Cloudflare)
 *
 * ⚠ Draft template — à valider par un avocat fintech FR avant la mise
 * en production publique. La structure et les bases légales sont
 * cependant tenues à jour à chaque évolution du modèle de données :
 * une nouvelle catégorie introduite côté backend doit apparaître
 * ci-dessous avant le déploiement.
 */
export default function Confidentialite() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink">
      <PublicNav />
      <main id="main" className="mx-auto max-w-3xl space-y-8 px-6 py-16 text-ink-muted">
        <header className="space-y-2">
          <h1 className="text-3xl font-bold text-ink">
            Politique de confidentialité
          </h1>
          <p className="text-sm text-ink-dim">
            Dernière mise à jour : 28 avril 2026 · Version 1
          </p>
        </header>

        <Block title="1. Responsable du traitement">
          <p>
            Le responsable du traitement au sens de l'article 4(7) du RGPD
            est <strong>{LEGAL.company.name}</strong>, joignable par
            courriel à{" "}
            <a
              href={`mailto:${LEGAL.contact.general}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.general}
            </a>
            .
          </p>
          <p>
            Pour toute question relative à tes données, tu peux contacter
            notre Délégué à la Protection des Données :{" "}
            <a
              href={`mailto:${LEGAL.contact.dpo}`}
              className="underline hover:text-ink"
            >
              {LEGAL.contact.dpo}
            </a>
            .
          </p>
        </Block>

        <Block title="2. Données collectées et bases légales">
          <p>
            Nous distinguons quatre catégories de données. Pour chacune,
            nous indiquons le but, la base légale (RGPD art. 6) et la
            durée de conservation.
          </p>
          <Table
            head={["Catégorie", "Données", "Finalité", "Base légale", "Conservation"]}
            rows={[
              [
                "Compte",
                "Email, mot de passe haché (bcrypt), pays de résidence déclaré",
                "Authentification, gestion du compte, géo-restriction réglementaire",
                "Exécution du contrat (CGU)",
                "Tant que le compte est actif. Suppression sur demande.",
              ],
              [
                "Profil & préférences",
                "Type de profil de trading, langue, devise, préférences notifications",
                "Personnalisation de l'expérience",
                "Exécution du contrat",
                "Tant que le compte est actif.",
              ],
              [
                "Activité de trading",
                "Signaux suivis, positions ouvertes, historique des ordres",
                "Affichage de l'activité, anti-fraude, calcul de la pause forcée 24h après 3 pertes",
                "Exécution du contrat + intérêt légitime (anti-fraude)",
                "Compte actif + 13 mois (recommandation CNIL trading) puis archivage anonyme.",
              ],
              [
                "Limites & conformité",
                "Confirmation 18+, statut de cooloff, plan d'abonnement",
                "Conformité réglementaire (CFTC, ANJ), gestion de l'auto-exclusion",
                "Obligation légale + intérêt légitime",
                "5 ans après clôture du compte (LCB-FT).",
              ],
            ]}
          />
        </Block>

        <Block title="3. Stockage local (localStorage)">
          <p>
            Les clés ci-dessous sont écrites dans le stockage local du
            navigateur. Elles sont indispensables au fonctionnement et
            sont exemptées du recueil de consentement (CNIL art. 82
            alinéa 2). Aucune donnée n'est transmise à un tiers sans
            ton consentement explicite.
          </p>
          <Table
            head={["Clé", "Contenu", "Durée"]}
            rows={[
              ["foresight.token", "Jeton JWT de session", "7 jours (expiration côté serveur)"],
              ["foresight.auth", "Email + plan + bornes de l'essai", "Session locale"],
              ["foresight.profile", "Profil de trading sélectionné", "Session locale"],
              ["foresight.positions", "Positions ouvertes pour réconciliation", "Tant que la position est ouverte"],
              ["foresight.settings", "Préférences notifications", "Session locale"],
              ["foresight.onboarding", "État d'onboarding", "Jusqu'à complétion"],
              ["foresight.cookieConsent", "Choix de cookies (cf. § 6)", "Indéfini, révocable depuis Paramètres"],
            ]}
          />
        </Block>

        <Block title="4. Sous-traitants et destinataires">
          <p>
            Les tiers suivants peuvent recevoir tes données dans le cadre
            strict de leur prestation. Aucune cession à des tiers
            commerciaux n'est effectuée.
          </p>
          <Table
            head={["Sous-traitant", "Rôle", "Localisation", "Données concernées"]}
            rows={[
              ["Polymarket Inc. (Builder Program)", "Routage des ordres et règlement on-chain en USDC", "États-Unis (Polygon network)", "Adresse Safe, montants, token markets"],
              ["Stripe Payments Europe Ltd.", "Encaissement de l'abonnement Pro", "Irlande (UE)", "Email, méthode de paiement, statut d'abonnement"],
              ["Google LLC (Sign in with Google)", "OAuth — connexion par compte Google (optionnel)", "États-Unis", "Email, identifiant Google"],
              ["Cloudflare Inc.", "CDN, anti-DDoS, géo-en-tête (cf-ipcountry)", "Réseau mondial — entrées UE prioritaires", "Adresse IP, en-têtes HTTP"],
              [
                LEGAL.hosting.name,
                "Hébergement de l'infrastructure",
                LEGAL.hosting.address,
                "Toutes les données serveur",
              ],
            ]}
          />
          <p>
            <strong>Transferts hors UE :</strong> Polymarket Inc. et
            Google LLC traitent des données aux États-Unis. Ces
            transferts s'appuient sur les Clauses Contractuelles Types
            de la Commission européenne (décision 2021/914) et, lorsque
            applicable, sur le DPF (Data Privacy Framework UE-US). Tu
            peux refuser le sign-in Google et continuer avec un compte
            email/mot de passe.
          </p>
        </Block>

        <Block title="5. Tes droits (RGPD art. 12 à 22)">
          <ul className="list-inside list-disc space-y-1.5">
            <li>
              <strong>Accès</strong> aux données te concernant — onglet
              Paramètres ou par courriel à{" "}
              <a
                href={`mailto:${LEGAL.contact.dpo}`}
                className="underline hover:text-ink"
              >
                {LEGAL.contact.dpo}
              </a>
              .
            </li>
            <li>
              <strong>Rectification</strong> de toute donnée inexacte —
              onglet Paramètres.
            </li>
            <li>
              <strong>Effacement</strong> (« droit à l'oubli ») — bouton
              « Supprimer mon compte » dans Paramètres → Zone danger.
              L'effacement est immédiat et irréversible côté Postgres.
              Les obligations de conservation 5 ans (LCB-FT) prévalent
              uniquement pour les comptes ayant exécuté des ordres réels.
            </li>
            <li>
              <strong>Limitation</strong> du traitement — par courriel.
            </li>
            <li>
              <strong>Portabilité</strong> (export JSON/CSV) — sur
              demande à <a
                href={`mailto:${LEGAL.contact.dpo}`}
                className="underline hover:text-ink"
              >
                {LEGAL.contact.dpo}
              </a>{" "}
              ; export CSV des positions disponible dans Paramètres.
            </li>
            <li>
              <strong>Opposition</strong> au traitement fondé sur
              l'intérêt légitime — par courriel.
            </li>
            <li>
              <strong>Réclamation</strong> auprès de la CNIL :{" "}
              <a
                href="https://www.cnil.fr/fr/plaintes"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-ink"
              >
                cnil.fr/fr/plaintes
              </a>
              .
            </li>
          </ul>
          <p className="mt-3 text-label-sm text-ink-dim">
            Les réponses à toute demande sont fournies sous 30 jours
            (art. 12 § 3 RGPD).
          </p>
        </Block>

        <Block title="6. Cookies et stockage local">
          <p>
            Foresight utilise le stockage local du navigateur (cf. § 3)
            uniquement pour le fonctionnement du Service — aucun cookie
            tiers de mesure d'audience ou de re-targeting n'est déposé
            sans ton accord. Tu peux à tout moment revoir tes choix
            depuis Paramètres → Zone danger ou consulter la{" "}
            <a href="/cookies" className="underline hover:text-ink">
              politique cookies dédiée
            </a>
            .
          </p>
        </Block>

        <Block title="7. Sécurité">
          <p>
            Les mots de passe sont hachés (bcrypt). Les jetons JWT
            expirent au bout de 7 jours. La connexion à l'API se fait
            exclusivement en HTTPS/TLS 1.2+. Une revue de sécurité
            interne est conduite à chaque introduction d'un nouveau
            sous-traitant.
          </p>
        </Block>

        <Block title="8. Modifications">
          <p>
            En cas d'évolution matérielle de cette politique, les
            utilisateurs sont informés par courriel et le bandeau de
            consentement cookies est ré-affiché lorsque les catégories
            changent.
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
