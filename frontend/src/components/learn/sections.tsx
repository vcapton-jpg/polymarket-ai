import {
  AlertTriangle,
  Check,
  Clock,
  ExternalLink,
  Flame,
  Gauge,
  Layers,
  Radio,
  Scale,
  ScanText,
  ShieldAlert,
  Target,
  TrendingDown,
  TrendingUp,
  Wallet,
  Zap,
} from "lucide-react"
import type { LearnContentBlocks } from "./LearnContent"
import {
  AnimatedFrise,
  ExampleCard,
  ExampleGrid,
  ExpertAppendix,
  Lede,
  LoopingLifeBar,
  Paragraph,
  PrimaryCallout,
  ScoreBars,
  type ScoreBar,
} from "./LearnVisuals"

/**
 * Chart / accent palette used by `ExampleCard`, `ScoreBars`, etc.
 * These hex values mirror tailwind tokens (see tailwind.config.ts):
 *   sky    -> chart-sky       (#60A5FA)
 *   orange -> chart-orange    (#F97316)
 *   purple -> chart-purple    (#A855F7)
 *   yes    -> chart-yes       (#4ADE80) — intentional: was #22C55E
 *   no     -> chart-no        (#F87171) — intentional: was #EF4444
 *   amber  -> chart-amber     (#FBBF24) — intentional: was #F59E0B
 *   mint   -> brand-300       (#5DFFCE) — intentional: was #6FF0C9
 *   brand  -> brand-500       (#0BE0A6)
 * Raw hexes remain here because consumers apply them as inline styles.
 */
const ACCENT = {
  sky: "#60A5FA",
  orange: "#F97316",
  purple: "#A855F7",
  yes: "#4ADE80",
  no: "#F87171",
  amber: "#FBBF24",
  mint: "#5DFFCE",
  brand: "#0BE0A6",
}

/* ───────────── Section ① Polymarket ───────────── */

const section1: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Imagine un marché sur <em>«&#x202F;La France gagne-t-elle la Coupe
          du monde 2026&#x202F;?&#x202F;»</em>. Le marché cote 15&#x202F;%. Tu
        y crois, tu achètes YES à 0,15&#x202F;USD. Si la France gagne, ta
        mise vaut 1,00&#x202F;USD — tu multiplies par 6,6.
      </Lede>
      <Paragraph>
        Polymarket applique ce principe à plus de 61&#x202F;000&#x202F;événements
        réels&#x202F;: élections, conflits, résultats sportifs, décisions
        économiques, avancées scientifiques.
      </Paragraph>
      <PrimaryCallout icon={Target}>
        Pas des actions. Pas des cryptos. Des événements réels.
      </PrimaryCallout>
      <a
        href="https://polymarket.com"
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-2 rounded-lg border border-brand-500/40 bg-brand-500/10 px-4 py-2 text-body-md font-semibold text-brand-300 transition-premium hover:border-brand-500/60 hover:bg-brand-500/15"
      >
        Ouvrir Polymarket
        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      </a>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Tu connais les paris sportifs&#x202F;? Polymarket fonctionne pareil,
        sauf qu’au lieu du foot tu paries sur{" "}
        <span className="text-ink">tout ce qui fait l’actualité</span>&#x202F;:
        élections, conflits, chiffres macro, grandes décisions.
      </Lede>
      <Paragraph>
        Le marché estime la France à 15&#x202F;% de chances de gagner la
        Coupe du monde. Un ticket YES coûte 0,15&#x202F;USD. Si la France
        gagne, ton ticket vaut 1,00&#x202F;USD — tu multiplies ta mise par{" "}
        <strong className="text-ink">6,6</strong>.
      </Paragraph>
      <ExampleGrid columns={3}>
        <ExampleCard
          eyebrow="Exemple"
          title="🗳️ Élection"
          body="Tu penses que Kamala Harris va gagner la primaire démocrate&#x202F;?"
          accent={ACCENT.sky}
        />
        <ExampleCard
          eyebrow="Exemple"
          title="₿ Crypto"
          body="Tu penses que Bitcoin atteindra 150&#x202F;000&#x202F;USD avant fin 2027&#x202F;?"
          accent={ACCENT.orange}
        />
        <ExampleCard
          eyebrow="Exemple"
          title="🏆 Sport"
          body="Tu penses que les Lakers gagneront la finale NBA&#x202F;?"
          accent={ACCENT.purple}
        />
      </ExampleGrid>
      <PrimaryCallout icon={Target}>
        Tu paries sur ce que tu comprends déjà — pas sur des graphiques
        financiers obscurs.
      </PrimaryCallout>
      <a
        href="https://polymarket.com"
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-2 rounded-lg border border-brand-500/40 bg-brand-500/10 px-4 py-2 text-body-md font-semibold text-brand-300 transition-premium hover:border-brand-500/60 hover:bg-brand-500/15"
      >
        Ouvrir Polymarket
        <ExternalLink className="h-3.5 w-3.5" aria-hidden />
      </a>
    </>
  ),
  expert: (
    <ExpertAppendix title="Mécanique de marché">
      <p>
        Polymarket est un <strong className="text-ink">AMM + order book
          hybride</strong> sur Polygon. Les outcome tokens (YES/NO) sont des
        ERC-1155 qui règlent à 1&#x202F;USDC à la résolution. Les LPs gagnent
        en market making&#x202F;; les traders accèdent via le CLOB ou la page
        marché.
      </p>
      <p>
        La résolution passe par l’UMA Optimistic Oracle (fenêtre de dispute
        de 7&#x202F;jours). Ne prends pas de position sur un marché dont la
        source de vérité n’est pas clairement définie dans la rubrique{" "}
        <em>resolution criteria</em>.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ② Opportunité ───────────── */

const section2: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Les marchés réagissent toujours avec du retard sur l’information.
      </Lede>
      <Paragraph>
        Quand une news éclate, il faut plusieurs minutes — parfois des
        heures — avant que les prix bougent sur Polymarket. Cette fenêtre,
        c’est ton opportunité.
      </Paragraph>
      <AnimatedFrise
        steps={[
          { label: "L’info sort", description: "Reuters, AP, AFP publient." },
          { label: "Notre pipeline", description: "Analyse en < 90\u00A0secondes." },
          { label: "Tu reçois l’alerte", description: "Telegram + dashboard." },
          { label: "Tu agis", description: "Avant la foule." },
          { label: "Le marché bouge", description: "Les prix se corrigent." },
          { label: "Tu sors", description: "Gain matérialisé." },
        ]}
      />
      <PrimaryCallout icon={Zap}>
        Foresight repère l’écart avant tout le monde. Tu agis. Le marché se
        corrige. Tu sors.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Les prix sur Polymarket ne bougent pas instantanément. Quand une
        grosse news tombe, il faut du temps aux traders pour la digérer et
        ajuster leurs positions.
      </Lede>
      <Paragraph>
        Ce retard, c’est ta <strong className="text-ink">fenêtre
          d’opportunité</strong>. Plus tu arrives tôt, mieux tu te
        positionnes.
      </Paragraph>
      <AnimatedFrise
        steps={[
          { label: "News" },
          { label: "Pipeline Foresight" },
          { label: "Alerte reçue" },
          { label: "Tu décides" },
          { label: "Le marché bouge" },
          { label: "Tu sors" },
        ]}
      />
      <PrimaryCallout icon={Zap}>
        Le job de Foresight, c’est de te prévenir pendant que les autres
        dorment encore.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Latence de marché mesurée">
      <p>
        Sur nos 12&#x202F;derniers mois de backtest, on mesure un lag médian
        de <strong className="text-ink">~7&#x202F;min</strong> entre la
        publication Reuters&#x202F;/&#x202F;AP et la première correction de
        prix significative (&gt;2&#x202F;% sur un marché tier-1). Tier-2&#x202F;:
        lag médian ~18&#x202F;min. Tier-3&#x202F;: ~40&#x202F;min.
      </p>
      <p>
        L’edge théorique est donc plus grand sur les tiers lents, à
        condition que la profondeur du marché le permette.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ③ RSS ───────────── */

const section3: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Reuters, AP, AFP publient chaque article en temps réel sur un fil
        public appelé <strong className="text-ink">flux RSS</strong>. On le
        lit automatiquement toutes les{" "}
        <strong className="text-ink">45&#x202F;secondes</strong>.
      </Lede>
      <Paragraph>
        C’est la source la plus rapide qui existe pour du contenu
        éditorialisé. Avant les applis. Avant les réseaux sociaux. Avant
        même la TV.
      </Paragraph>
      <ExampleGrid columns={3}>
        <ExampleCard
          eyebrow="Agence"
          title="Reuters"
          body="Couverture globale · ~2\u00A0000 articles/jour."
          accent={ACCENT.amber}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="Agence"
          title="AP"
          body="Forte densité US\u00A0· politique, sport."
          accent={ACCENT.sky}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="Agence"
          title="AFP"
          body="Europe, Afrique, géopolitique."
          accent={ACCENT.yes}
          icon={Radio}
        />
      </ExampleGrid>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Un <strong className="text-ink">flux RSS</strong>, c’est une liste
        d’articles publiée automatiquement par un média dès qu’il sort une
        info. Pas besoin d’ouvrir un site ou une appli — c’est une «&#x202F;radio&#x202F;»
        invisible qui annonce chaque nouvelle news en quelques secondes.
      </Lede>
      <Paragraph>
        On lit ceux de Reuters, AP et AFP toutes les{" "}
        <strong className="text-ink">45&#x202F;secondes</strong>. Plus rapide
        que n’importe quelle autre source grand public.
      </Paragraph>
      <ExampleGrid columns={3}>
        <ExampleCard
          eyebrow="Agence"
          title="Reuters"
          body="La référence mondiale en news éditoriale."
          accent={ACCENT.amber}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="Agence"
          title="AP"
          body="Grosse couverture US, sport, politique."
          accent={ACCENT.sky}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="Agence"
          title="AFP"
          body="Europe, géopolitique, et beaucoup de couverture francophone."
          accent={ACCENT.yes}
          icon={Radio}
        />
      </ExampleGrid>
      <PrimaryCallout icon={Zap}>
        On est branchés 24/7 sur les «&#x202F;radios&#x202F;» officielles du
        journalisme mondial.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Architecture de collecte">
      <p>
        Les feeds sont ingérés par un worker Python async (FastAPI +
        aiohttp), déduppés par URL et hash de titre, puis embeddés via
        <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
          text-embedding-3-small
        </code>
        . Chaque article est matché contre les{" "}
        <strong className="text-ink">marchés actifs</strong> via pgvector{" "}
        <em>ivfflat</em> (cosine) + re-ranking par règles métier.
      </p>
      <p>
        Latence RSS → signal scoré&#x202F;:{" "}
        <strong className="text-ink">~85&#x202F;secondes</strong> (p50),
        ~130&#x202F;s (p95).
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ④ Tiers ───────────── */

const section4: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Toutes les sources ne se valent pas. On classe chaque source dans
        l’un des trois tiers selon sa <strong className="text-ink">fiabilité
        historique</strong> : c’est ce qui détermine le poids qu’elle prend
        dans le score d’un signal.
      </Lede>
      <ExampleGrid columns={3}>
        <ExampleCard
          eyebrow="TIER-1"
          title="Agences de presse"
          body="Reuters, Bloomberg, AP, AFP, FT, WSJ. Pipeline éditorial direct, fact-checking rigoureux, premier accès aux dépêches officielles."
          accent={ACCENT.yes}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="TIER-2"
          title="Médias spécialisés & comptes vérifiés"
          body="Politico, The Economist, comptes Twitter/X vérifiés (journalistes, officiels, watchlists reconnues). Fiables mais secondaires."
          accent={ACCENT.amber}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="TIER-3"
          title="Agrégateurs & médias locaux"
          body="Blogs, médias régionaux, comptes non vérifiés. Jamais source unique d’un signal — utilisés comme signal d’appui uniquement."
          accent={ACCENT.no}
          icon={Radio}
        />
      </ExampleGrid>
      <Paragraph>
        Quand tu ouvres un signal, le nombre de sources Tier-1 est affiché
        dans le footer de la carte. Deux sources Reuters valent toujours
        plus qu’une seule, même au même score : la corroboration réduit le
        risque de faux positif.
      </Paragraph>
      <PrimaryCallout icon={Target}>
        Le tier de la source est l’un des 6 composants du score (18 pourcent
        du poids). Plus un signal s’appuie sur des Tier-1, plus sa
        crédibilité monte.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Imagine que tu reçois deux nouvelles en même temps : une de
        Reuters, une d’un blog anonyme. Laquelle crois-tu en premier ?
      </Lede>
      <Paragraph>
        On fait exactement ce raisonnement pour chaque source. On a défini
        trois niveaux de confiance.
      </Paragraph>
      <ExampleGrid columns={3}>
        <ExampleCard
          eyebrow="TIER-1"
          title="Sources officielles"
          body="Reuters, AP, Bloomberg, AFP. Ce sont les agences de presse mondiales — elles vérifient avant de publier."
          accent={ACCENT.yes}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="TIER-2"
          title="Médias de confiance"
          body="Politico, journalistes vérifiés sur X, sources spécialisées reconnues. Généralement fiables, mais on double-vérifie."
          accent={ACCENT.amber}
          icon={Radio}
        />
        <ExampleCard
          eyebrow="TIER-3"
          title="Sources secondaires"
          body="Blogs, comptes inconnus. On les surveille pour être complets, mais on ne déclenche jamais un signal sur eux seuls."
          accent={ACCENT.no}
          icon={Radio}
        />
      </ExampleGrid>
      <PrimaryCallout icon={Target}>
        Pour un signal solide, cherche au moins 2 sources Tier-1. C’est
        visible directement sur la carte — clique pour voir les détails.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Pondération par tier dans le modèle">
      <p>
        Le poids source est un scalaire dans [0.6, 1.0] appliqué au
        composant <em>crédibilité</em> du score (18 % du total) :
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong className="text-ink">Tier-1</strong> — poids 0.90–1.00.
          Reuters, Bloomberg, AP, AFP, FT, WSJ. Lag médian de correction de
          prix : ~7 min.
        </li>
        <li>
          <strong className="text-ink">Tier-2</strong> — poids 0.70–0.89.
          Politico, The Economist, comptes X vérifiés (journalistes accrédités,
          watchlists institutionnelles). Lag médian : ~18 min.
        </li>
        <li>
          <strong className="text-ink">Tier-3</strong> — poids 0.60–0.69.
          Agrégateurs, blogs, comptes non vérifiés. Lag médian : ~40 min.
          Signal d’appui uniquement — le pipeline bloque tout signal
          mono-source Tier-3.
        </li>
      </ul>
      <p>
        La liste des sources par tier est maintenue manuellement et
        recalibrée trimestriellement sur la base des vrais positifs/négatifs
        de chaque source sur la période.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑤ Score ───────────── */

const scoreBars: ScoreBar[] = [
  {
    label: "Pertinence de la news",
    description:
      "À quel point l’article matche le marché. Une news directe (même acteur, même événement) scope beaucoup plus qu’une news connexe.",
    weight: 0.25,
    color: ACCENT.yes,
    technicalWeight: "0.25 · cosine similarity embedding",
  },
  {
    label: "Fraîcheur",
    description:
      "Plus la news est récente, plus le score monte. Une news de 2\u00A0heures pèse plus qu’une news de 24\u00A0heures.",
    weight: 0.2,
    color: ACCENT.mint,
    technicalWeight: "0.20 · exp(-age_minutes / 60)",
  },
  {
    label: "Crédibilité de la source",
    description:
      "Reuters, AP, AFP pèsent plus qu’un blog. Chaque agence a un score de confiance historique.",
    weight: 0.18,
    color: ACCENT.sky,
    technicalWeight: "0.18 · poids source (0.6–1.0)",
  },
  {
    label: "Écart prix/probabilité estimée",
    description:
      "Plus le marché est mispriced par rapport à notre estimation, plus le score monte.",
    weight: 0.17,
    color: ACCENT.amber,
    technicalWeight: "0.17 · |p_market − p_est|",
  },
  {
    label: "Liquidité du marché",
    description:
      "Un signal sur un marché profond est plus facile à exécuter. On évite les signaux sur marchés vides.",
    weight: 0.12,
    color: ACCENT.purple,
    technicalWeight: "0.12 · log(volume_24h + 1)",
  },
  {
    label: "Momentum récent",
    description:
      "Si le prix a déjà commencé à bouger, le signal est plus tardif. Si le marché est encore immobile, il est plus frais.",
    weight: 0.08,
    color: ACCENT.orange,
    technicalWeight: "0.08 · 1 − |∆p_30min|",
  },
]

const section5: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Chaque signal reçoit un score de <strong className="text-ink">0 à
          100</strong>, recalculé en continu à partir de 6&#x202F;variables.
        Plus le score est haut, plus le signal est actionnable.
      </Lede>
      <ScoreBars bars={scoreBars} />
      <PrimaryCallout icon={Gauge}>
        Score &gt;&#x202F;75 = «&#x202F;Signal fort&#x202F;». Score
        &gt;&#x202F;90 = «&#x202F;Exceptionnel&#x202F;». Le label apparaît à
        côté du score sur chaque card.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Chaque signal reçoit une <strong className="text-ink">note de 0 à
          100</strong>. Plus c’est élevé, plus c’est intéressant.
      </Lede>
      <Paragraph>
        Cette note ne sort pas de nulle part. Elle mélange 6 ingrédients
        qu’on affiche en toute transparence ci-dessous.
      </Paragraph>
      <ScoreBars bars={scoreBars} />
      <PrimaryCallout icon={Gauge}>
        À retenir : au-dessus de 75, le signal a un bon profil. Au-dessus
        de 90, c’est rare et exceptionnel.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Poids exacts du modèle de scoring">
      <ul className="list-disc space-y-1 pl-5">
        {scoreBars.map((b) => (
          <li key={b.label}>
            <strong className="text-ink">{b.label}</strong> — {b.technicalWeight}
          </li>
        ))}
      </ul>
      <p>
        Le modèle est une régression pondérée calibrée sur 18 mois
        d’historique. Recalibration mensuelle, hold-out 20%.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑥ Barre de vie ───────────── */

const section6: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Une opportunité a une durée de vie limitée. Dès que le marché
        commence à digérer l’info, l’edge disparaît. La barre de vie
        visualise ce compte à rebours.
      </Lede>
      <LoopingLifeBar />
      <Paragraph>
        <strong className="text-ink">Verte</strong> → l’opportunité est
        encore fraîche.{" "}
        <strong className="text-signal-amber">Orange</strong> → le marché
        commence à bouger, agis vite.{" "}
        <strong className="text-signal-no">Rouge</strong> → l’edge est
        consommé, ne rentre plus.
      </Paragraph>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Un signal, c’est comme une glace en été : ça fond. Tu as une
        fenêtre pour agir, puis ça devient moins intéressant.
      </Lede>
      <Paragraph>
        Pour que tu voies d’un coup d'œil si tu es encore dans la fenêtre,
        chaque signal a une <strong className="text-ink">barre de
          vie</strong>. Elle part de 100% et descend avec le temps.
      </Paragraph>
      <LoopingLifeBar />
      <PrimaryCallout icon={Clock}>
        Règle simple : si la barre est rouge, laisse passer. Tu auras
        d’autres signaux.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Modèle de décroissance">
      <p>
        La life bar combine deux signaux :
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong className="text-ink">Décroissance temporelle</strong>{" "}
          exponentielle <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            exp(-t / τ)
          </code>{" "}
          avec τ calibré par tier (tier-1 : 20 min ; tier-2 : 45 min ;
          tier-3 : 90 min).
        </li>
        <li>
          <strong className="text-ink">Drift de prix observé</strong> depuis
          l’émission — quand le marché a bougé de ≥ 60% du spread estimé, on
          considère l’opportunité consommée même si le temps n’est pas
          écoulé.
        </li>
      </ul>
      <p>
        La vraie barre de vie recalcule sur le front toutes les 2 secondes
        depuis un timestamp d’émission en UTC.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑦ Vendre ───────────── */

const sellConditions = [
  {
    eyebrow: "① Objectif atteint",
    title: "Take-profit +30%",
    body: "Si ton gain estimé dépasse +30% du capital investi, on bascule la position en 🔴 Vendre.",
    accent: ACCENT.yes,
    icon: TrendingUp,
  },
  {
    eyebrow: "② Stop-loss",
    title: "Repli > 15%",
    body: "Si le prix recule de plus de 15% par rapport à ton entrée, on protège le capital restant.",
    accent: ACCENT.no,
    icon: TrendingDown,
  },
  {
    eyebrow: "③ Temps écoulé",
    title: "Barre de vie à 0%",
    body: "L’opportunité est consommée. Sors, le ratio rendement/temps n’est plus attractif.",
    accent: ACCENT.amber,
    icon: Clock,
  },
  {
    eyebrow: "④ News contraire",
    title: "Retournement",
    body: "Une nouvelle info matérielle contredit la thèse initiale : on alerte immédiatement.",
    accent: ACCENT.purple,
    icon: Flame,
  },
]

const section7: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        On ne te laisse pas seul avec ta position. Quatre conditions
        basculent le statut en <span className="text-signal-no">🔴 Vendre</span>{" "}
        automatiquement.
      </Lede>
      <ExampleGrid columns={2}>
        {sellConditions.map((c) => (
          <ExampleCard key={c.title} {...c} />
        ))}
      </ExampleGrid>
      <PrimaryCallout icon={Target}>
        Quand une position passe en 🔴, tu reçois une notification{" "}
        <strong className="text-ink">browser</strong> ET{" "}
        <strong className="text-ink">Telegram</strong>. Tu décides — on
        déclenche rien à ta place.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Savoir quand <strong className="text-ink">sortir</strong>, c’est
        aussi important que savoir quand entrer. On a défini 4 règles
        simples pour ne jamais te laisser face à l’incertitude.
      </Lede>
      <ExampleGrid columns={2}>
        {sellConditions.map((c) => (
          <ExampleCard key={c.title} {...c} />
        ))}
      </ExampleGrid>
      <PrimaryCallout icon={Target}>
        Dès qu’une de ces 4 règles s’active, ton téléphone sonne. Tu n’as
        rien à vérifier toi-même.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Paramètres configurables côté Pro">
      <p>
        Les seuils sont hardcodés en V2 (+30% / −15% / barre à 0%). En Pro,
        tu pourras personnaliser par position :
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>Take-profit en %</li>
        <li>Trailing stop (nouveau, sur drift de prix relatif)</li>
        <li>Time-stop custom (override de la life bar)</li>
        <li>Webhook de sortie (routing vers ton propre système)</li>
      </ul>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑧ Risques ───────────── */

const section8: LearnContentBlocks = {
  standard: (
    <>
      <PrimaryCallout icon={ShieldAlert} tone="warning">
        Oui. Comme tout investissement.
      </PrimaryCallout>
      <Paragraph>
        Foresight ne garantit aucun résultat. On détecte des opportunités
        basées sur des faits — mais les marchés peuvent surprendre. Une
        news peut être démentie. Une position peut partir dans le mauvais
        sens. Un marché peut rester mispriced plus longtemps que ta
        patience.
      </Paragraph>
      <Paragraph>
        Notre rôle est de <strong className="text-ink">t’informer vite</strong>,
        pas de décider à ta place.
      </Paragraph>
      <PrimaryCallout icon={AlertTriangle} tone="danger">
        Ne mise jamais plus que ce que tu peux perdre.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <PrimaryCallout icon={ShieldAlert} tone="warning">
        Oui, il y a un risque. Toujours.
      </PrimaryCallout>
      <Paragraph>
        On préfère te le dire clairement : il est{" "}
        <strong className="text-ink">totalement possible de perdre ta
          mise</strong>. Un signal bien noté peut tourner au ralenti, ou
        dans le mauvais sens.
      </Paragraph>
      <Paragraph>
        Notre job est de te donner une info fiable et rapide. Pas de te
        garantir des gains. Les gains garantis, ça n’existe pas.
      </Paragraph>
      <PrimaryCallout icon={AlertTriangle} tone="danger">
        Règle d’or : ne mets jamais sur Polymarket ce que tu ne peux pas
        perdre sans stresser.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Math du capital & garde-fous">
      <p>
        <strong className="text-ink">Kelly criterion</strong> — taille de
        mise ={" "}
        <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
          edge / odds
        </code>
        , clampé à{" "}
        <strong className="text-ink">≤ 25% Kelly</strong> (quart-Kelly).
        Le full-Kelly optimise la croissance géométrique mais expose à des
        drawdowns ingérables dès que l’edge est mal estimé — et ton edge
        l’est toujours un peu.
      </p>
      <p>
        <strong className="text-ink">Expected value</strong> —{" "}
        <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
          EV = P(win) × (payout − stake) − P(lose) × stake
        </code>
        . Règle de sanity : si l’EV est ≤ 0 net de frais et de slippage,
        tu ne rentres pas. L’espoir n’est pas une thèse.
      </p>
      <p>
        <strong className="text-ink">Drawdown management</strong> — règle
        dure : après −20% de drawdown sur une fenêtre glissante de 30
        jours, tu arrêtes toute nouvelle position pendant 7 jours. Le but
        n’est pas de se punir, c’est de couper le biais émotionnel qui
        suit une série perdante.
      </p>
      <p>
        <strong className="text-ink">Corrélations cachées</strong> — trois
        signaux dans la même catégorie (même élection, même conflit, même
        secteur) ne sont pas trois paris indépendants : ils partagent le
        même facteur de risque. Plafonne l’exposition par catégorie à{" "}
        <strong className="text-ink">30% du capital</strong>, tous signaux
        confondus.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑨ FAQ ───────────── */

const faqItems: Array<{ q: string; a: React.ReactNode }> = [
  {
    q: "Polymarket est-il légal aux États-Unis ?",
    a: (
      <>
        Polymarket n’accepte pas d’utilisateurs US depuis l’accord de 2022
        avec la CFTC. Les résidents US techniquement-capables utilisent des
        VPN — à leurs risques. Foresight ne donne pas de conseil juridique,
        renseigne-toi dans ta juridiction avant toute activité.
      </>
    ),
  },
  {
    q: "Comment sont imposés mes gains Polymarket aux US ?",
    a: (
      <>
        Aux US, les gains Polymarket sont traités comme des gains de
        cryptomonnaies (capital gains ordinaire ou long-term selon la durée
        de détention). Consulte un CPA — chaque situation est différente.
      </>
    ),
  },
  {
    q: "Ai-je besoin de faire un KYC pour utiliser Polymarket ?",
    a: (
      <>
        Non, Polymarket n’impose pas de KYC classique. Tu connectes un
        wallet, tu déposes en USDC, tu trades. C’est l’un des arguments de
        vente de la plateforme vs les bookmakers classiques.
      </>
    ),
  },
  {
    q: "Comment déposer de l’argent sur Polymarket ?",
    a: (
      <>
        Le dépôt se fait en USDC sur le réseau Polygon. Tu peux acheter de
        l’USDC sur Coinbase, Kraken, Binance ou directement via MoonPay
        depuis l’interface Polymarket. Bridge USDC → Polygon, puis transfert
        vers ton wallet Polymarket.
      </>
    ),
  },
  {
    q: "Comment retirer mes gains ?",
    a: (
      <>
        Inverse du dépôt : bridge USDC Polygon → réseau où ton exchange
        accepte les dépôts (Ethereum, Arbitrum...), puis conversion en fiat
        depuis l’exchange. Prévoir 5 à 15 minutes et quelques dollars de gas.
      </>
    ),
  },
  {
    q: "Foresight est-il régulé ?",
    a: (
      <>
        Foresight est un <strong className="text-ink">outil
          d’information</strong> — on ne gère pas tes fonds, on ne prend
        aucune décision d’exécution à ta place. À ce titre on n’a pas
        besoin d’un agrément type broker/dealer. Les décisions de trade
        restent 100% de ton côté.
      </>
    ),
  },
  {
    q: "Foresight collecte-t-il une commission sur mes trades ?",
    a: (
      <>
        Non. Aucune commission sur tes trades. On est inscrits au{" "}
        <strong className="text-ink">Polymarket Builder Program</strong> — on
        reçoit une rétrocession de Polymarket sur les volumes générés via
        notre interface, sans prélèvement additionnel sur tes gains.
      </>
    ),
  },
  {
    q: "Que se passe-t-il si un marché n’est pas résolu ?",
    a: (
      <>
        Polymarket utilise l’Optimistic Oracle d’UMA avec une fenêtre de
        dispute de 7 jours. Si la résolution est contestée, elle peut
        prendre plus de temps — mais c’est rare (&lt; 1% des marchés).
      </>
    ),
  },
  {
    q: "Comment contacter le support ?",
    a: (
      <>
        Par email à <span className="text-ink">support@foresight.trade</span>.
        Réponse sous 24h ouvrées. Pour les urgences Pro, un canal Telegram
        dédié est ouvert avec réponse médiane de 2h.
      </>
    ),
  },
]

const section9: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Les questions qu’on nous pose le plus souvent, groupées par
        thématique. Si ta question n’est pas là, écris-nous directement.
      </Lede>
      <FAQAccordion items={faqItems} />
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Les questions qu’on nous pose le plus souvent, groupées par
        thématique. Si ta question n’est pas là, écris-nous directement.
      </Lede>
      <div className="border-l-2 border-brand-500/40 bg-brand-500/[0.04] pl-4 py-2 text-[0.9375rem] italic text-ink/90">
        Commence par les bases : où est ton argent, qui garantit les
        paris, comment tu récupères tes gains. La fiscalité et le KYC
        viennent après — tu n’as pas besoin de tout comprendre pour
        ouvrir ta première position de 5 USDC.
      </div>
      <FAQAccordion items={faqItems} />
    </>
  ),
}

/* ───────────── FAQ Accordion (used only in section ⑨) ───────────── */

function FAQAccordion({ items }: { items: typeof faqItems }) {
  return (
    <ul className="divide-y divide-line/60 rounded-2xl border border-line-strong bg-obsidian-850/40">
      {items.map((item, i) => (
        <li key={i} className="group">
          <details className="group">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-[0.9375rem] font-medium text-ink transition-premium hover:bg-obsidian-800/40">
              <span>{item.q}</span>
              <span
                className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-line-strong bg-obsidian-900 text-label-sm text-ink-muted transition-premium group-open:rotate-45 group-open:border-brand-500/40 group-open:text-brand-300"
                aria-hidden
              >
                +
              </span>
            </summary>
            <div className="px-5 pb-4 text-body-md leading-relaxed text-ink-muted">
              {item.a}
            </div>
          </details>
        </li>
      ))}
    </ul>
  )
}

/* ───────────── Section ⑥ Lire une fiche signal ─────────────
 *
 * Anchored in chapter 2 (Décoder), this section maps the four visual
 * zones of a signal card to "what each one tells you" in plain French.
 * Discoverer-mode replaces jargon with everyday vocabulary; the expert
 * appendix names the underlying components for users who'll later wire
 * the API.
 */

const signalZones = [
  {
    title: "Header",
    body: "Le titre du marché, le tier de la source, le timestamp d’émission. C’est le « quoi, qui, quand ».",
    icon: Layers,
    accent: ACCENT.sky,
  },
  {
    title: "Score",
    body: "Le 0–100 et son label (Modéré, Fort, Exceptionnel). C’est notre conviction synthétique.",
    icon: Gauge,
    accent: ACCENT.purple,
  },
  {
    title: "Sources",
    body: "Les 1 à 3 dépêches qui ont déclenché le signal. Cliquables — toujours vérifier au moins une.",
    icon: Radio,
    accent: ACCENT.amber,
  },
  {
    title: "Marché & prix",
    body: "Le côté à prendre (YES/NO), le prix actuel, la barre de vie. C’est l’info opérationnelle.",
    icon: Target,
    accent: ACCENT.brand,
  },
]

const sectionLireSignal: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Une fiche signal est découpée en{" "}
        <strong className="text-ink">4 zones</strong>. Chacune répond à une
        question précise : <em>quoi</em>, <em>combien</em>, <em>pourquoi</em>,{" "}
        <em>où</em>.
      </Lede>
      <ExampleGrid columns={2}>
        {signalZones.map((z) => (
          <ExampleCard key={z.title} {...z} />
        ))}
      </ExampleGrid>
      <PrimaryCallout icon={ScanText}>
        L’ordre n’est pas décoratif — c’est l’ordre dans lequel ton œil
        doit balayer la card pour décider en moins de 10&#x202F;secondes.
      </PrimaryCallout>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        Tu n’as pas besoin de tout lire en détail. Une fiche signal est
        toujours organisée pareil — quatre zones, dans le même ordre.
      </Lede>
      <Paragraph>
        Voici comment les pros lisent une carte en moins de 10&#x202F;secondes.
        Le but : décider sans deviner.
      </Paragraph>
      <ExampleGrid columns={2}>
        {signalZones.map((z) => (
          <ExampleCard key={z.title} {...z} />
        ))}
      </ExampleGrid>
      <PrimaryCallout icon={ScanText}>
        Astuce : si une zone te manque (par exemple, pas de source
        cliquable visible), considère le signal comme incomplet et passe
        au suivant.
      </PrimaryCallout>
    </>
  ),
  expert: (
    <ExpertAppendix title="Mapping vers le payload API">
      <p>
        Chaque zone est rendue depuis un sous-objet du payload{" "}
        <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
          /api/signals/:id
        </code>{" "}
        :
      </p>
      <ul className="list-disc space-y-1 pl-5">
        <li>
          <strong className="text-ink">Header</strong> →{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            market.title
          </code>
          ,{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            sources[0].tier
          </code>
          ,{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            emitted_at
          </code>
          .
        </li>
        <li>
          <strong className="text-ink">Score</strong> →{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            score.value
          </code>{" "}
          + label dérivé côté front (cf. section 5).
        </li>
        <li>
          <strong className="text-ink">Sources</strong> →{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            sources[]
          </code>{" "}
          (toujours triées par tier croissant — le tier-1 est en
          premier).
        </li>
        <li>
          <strong className="text-ink">Marché & prix</strong> →{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            recommendation.side
          </code>
          ,{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            market.price
          </code>
          ,{" "}
          <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
            life_bar.value
          </code>
          .
        </li>
      </ul>
    </ExpertAppendix>
  ),
}

/* ───────────── Section ⑧ Combien miser ? ─────────────
 *
 * The first action-oriented section in chapter 3. We explicitly call
 * out the 1–3% rule because it is the single behavioural change that
 * has the largest impact on long-term outcomes — far more than any
 * model improvement on our side.
 */

const sectionPositionSizing: LearnContentBlocks = {
  standard: (
    <>
      <Lede>
        Règle de base&#x202F;:{" "}
        <strong className="text-ink">1 à 3&#x202F;% de ton bankroll</strong>{" "}
        par signal. Pas plus, même quand le score est de 95.
      </Lede>
      <Paragraph>
        Pourquoi&#x202F;? Parce qu’un score élevé ne supprime pas le
        risque — il le rend juste meilleur en moyenne. Sur 50 signaux
        notés 90+, il y en aura toujours 5 à 10 qui partent dans le mur.
        Ta taille de mise doit pouvoir absorber cette série sans casser
        le bankroll.
      </Paragraph>
      <PrimaryCallout icon={Scale}>
        Bankroll de 200&#x202F;USDC → mise type =
        2&#x202F;USDC à 6&#x202F;USDC. Bankroll de 2&#x202F;000&#x202F;USDC →
        20 à 60&#x202F;USDC. C’est inconfortablement petit. C’est
        normal&#x202F;: c’est ce qui te garde dans le jeu.
      </PrimaryCallout>
      <Paragraph>
        Tu pourras moduler dans cette fenêtre selon le score&#x202F;:
        ~1&#x202F;% pour un signal entre 70 et 80, ~2&#x202F;% entre 80
        et 90, ~3&#x202F;% au-dessus de 90. Mais ne sors jamais de la
        fenêtre.
      </Paragraph>
    </>
  ),
  discoverer: (
    <>
      <Lede>
        La question n’est pas «&#x202F;quel signal prendre&#x202F;?&#x202F;»
        mais{" "}
        <strong className="text-ink">«&#x202F;combien je mets dessus&#x202F;?&#x202F;»</strong>.
        C’est ce qui sépare ceux qui durent de ceux qui crament leur
        compte en deux semaines.
      </Lede>
      <Paragraph>
        La règle qu’on te donne est simple et un peu frustrante&#x202F;:
        ne mets jamais plus de 3&#x202F;% de ce que tu as déposé sur un
        seul signal. Même si tu es certain. Surtout si tu es certain.
      </Paragraph>
      <PrimaryCallout icon={Wallet}>
        Tu as déposé 100&#x202F;USDC&#x202F;? Mise type =
        1 à 3&#x202F;USDC par signal. Oui, c’est petit. C’est le prix de
        rester en jeu six mois plus tard.
      </PrimaryCallout>
      <Paragraph>
        Tu vas avoir envie de mettre plus quand un signal te paraît
        évident. C’est le piège&#x202F;: tout le monde le ressent, et
        c’est exactement quand on perd le plus.
      </Paragraph>
    </>
  ),
  expert: (
    <ExpertAppendix title="Cadre quantitatif — Kelly fractionnaire">
      <p>
        La règle 1–3&#x202F;% est une approximation conservative de
        Kelly fractionnaire. La taille optimale est{" "}
        <code className="mx-1 rounded bg-obsidian-800 px-1 py-0.5 text-body-sm text-ink">
          f* = (p · b − q) / b
        </code>{" "}
        avec{" "}
        <em>p</em> = proba de gain estimée,{" "}
        <em>b</em> = payout net (en multiples de la mise),{" "}
        <em>q = 1 − p</em>.
      </p>
      <p>
        En pratique on applique{" "}
        <strong className="text-ink">¼ Kelly</strong>{" "}
        — le full-Kelly suppose que ton estimation de <em>p</em> est
        exacte, ce qui n’arrive jamais. La fraction ¼ amortit l’erreur
        d’estimation tout en conservant une croissance géométrique
        positive sur l’historique back-testé.
      </p>
      <p>
        Garde-fou supplémentaire&#x202F;:{" "}
        <strong className="text-ink">corrélation des positions</strong>.
        Deux signaux sur le même événement (par ex. deux marchés
        d’élection américaine) ne comptent pas pour deux positions —
        traite-les comme une seule pour le sizing.
      </p>
    </ExpertAppendix>
  ),
}

/* ───────────── Final CTA (shown on the index page) ───────────── */

export function IndexCTA() {
  return (
    <div className="rounded-2xl border border-brand-500/30 bg-gradient-to-br from-brand-500/10 via-obsidian-850/40 to-obsidian-850/40 px-5 py-5 md:px-6 md:py-6">
      <p className="mb-1 font-mono text-label-xs uppercase tracking-[0.14em] text-brand-300">
        Tu sais maintenant
      </p>
      <h3 className="mb-3 font-display text-title-sm font-semibold text-ink md:text-title-md">
        Comment ça marche.
      </h3>
      <a
        href="/signals"
        className="inline-flex items-center gap-2 rounded-lg border border-brand-500/40 bg-brand-500/15 px-4 py-2 text-body-md font-semibold text-brand-200 transition-premium hover:border-brand-500/60 hover:bg-brand-500/25"
      >
        Voir les signaux en direct
        <Check className="h-3.5 w-3.5" aria-hidden />
      </a>
    </div>
  )
}

/* ───────────── Public registry ───────────── */

export const LEARN_CONTENT: Record<string, LearnContentBlocks> = {
  // Chapitre 1 · Comprendre
  polymarket: section1,
  opportunite: section2,
  rss: section3,
  tiers: section4,
  // Chapitre 2 · Décoder
  score: section5,
  "lire-signal": sectionLireSignal,
  "barre-vie": section6,
  // Chapitre 3 · Agir
  "position-sizing": sectionPositionSizing,
  vendre: section7,
  risques: section8,
  faq: section9,
}
