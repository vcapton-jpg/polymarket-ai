# Polymarket AI — Backlog consolidé des problèmes

> Toutes les issues soulevées pendant la session d'audit 2026-04-23.
> Source : conversation Claude Code + audit externe pasté par l'utilisateur.
> Statut : non commencé sauf mention contraire.
>
> Légende sévérité : 🔴 Critique · 🟠 Haute · 🟡 Moyenne · 🔵 Basse

---

## 0. Contexte & décisions produit

### 0.1 Pivot produit décidé — "Learn & Trade"
- **Décision** : garder le trading réel (builder program Polymarket), positionner sur "jeunes qui investissent en apprenant"
- **Caveat explicite** : le builder program Polymarket ne donne **pas** de cover réglementaire FR. Polymarket est bloqué par l'ANJ depuis fin 2024. Risque légal FR non résolu.
- **Mix validé** : paper trading en onboarding obligatoire + trading réel plafonné + gamification éducative
- **Plan à rédiger** : `docs/superpowers/plans/2026-04-23-pivot-learn-and-trade.md`

### 0.2 État pipeline
- 🔴 **Pipeline dark depuis 6 jours** — aucun signal généré, aucune capture outcome
- Impact : toute mesure actuelle est figée sur un dataset ancien

### 0.3 Décisions de gel
- **Interdit 10 jours** : poids `HeuristicScorer`, prompts LLM production, seuils `signal_score_threshold` / `signal_min_cosine_score` / `hard_exclusion_*`
- **Objectif gel** : collecte propre pour mesures fiables à J+10

---

## 1. Trous méthodologiques — les mesures sont invalides

Tout tuning basé sur les chiffres actuels est du guess work.

### 1.1 🔴 Dédup simhash casse le `confirmation score`
- **Problème** : une news AFP reprise par Le Monde, Figaro, 20 Minutes produit 3 simhash différents (reformulations) → cluster à 3 sources au lieu de 1 vraie → `confirmation_score` monte artificiellement de 0.7 à 1.0
- **Fix** : remplacer simhash par near-dup embedding (cosine ≥ 0.95 sur `news_clean.embedding`, lookback 24h, même bucket)
- **Chantier 2 du prompt d'audit**

### 1.2 🔴 `min_articles_per_event = 1`
- **Problème** : un event = 1 seul article n'est pas un cluster. Combiné à 1.1, déclenche signal sur news isolée tier-2 avec `confirmation` surestimée
- **Fix** : `min_articles_per_event = 2` + nouveau setting `min_unique_sources_per_event = 2`
- **Chantier 2 du prompt d'audit**

### 1.3 🔴 Divergence `clustering_cosine_threshold` — 0.75 (doc) vs 0.82 (code)
- **Problème** : valeur réelle runtime non tracée → on ne sait pas quel threshold a tourné sur le dataset historique
- **Fix** : grep config → code, aligner, documenter la vraie valeur active pendant la collecte passée
- **Chantier 1 du prompt d'audit**
- **Meta-issue** : probablement d'autres divergences config/doc à auditer

### 1.4 🔴 Pas de baseline naïve
- **Problème** : winrate 46-48% sans baseline ne veut rien dire. Il faut comparer à :
  - Baseline 0 : random YES/NO → ~50%
  - Baseline 1 : momentum (direction du dernier mouvement ≥2%)
  - Baseline 2 : multi-source (YES si ≥2 tier-1 mentionnent l'entité dans les 2h)
- **Fix** : colonnes `baseline_*` sur `signal_outcomes`, calcul parallèle à chaque signal
- **Chantier 3 du prompt d'audit**

### 1.5 🔴 Significativité statistique absente
- **Problème** : n=22/n=24 sur le bucket 75-89 a un IC95 énorme. BUY_YES 29.2% → IC95 ≈ [13%, 51%]. Peut être du bruit pur
- **Fix** : pas d'overlay/patch tant que n≥30 par cellule. Ajouter p-value + IC sur dashboard
- **Chantier 5 du prompt d'audit**

---

## 2. Biais LLM — hypothèse directionnelle

### 2.1 🟠 Biais pro-YES de GPT-4o (hypothèse prioritaire)
- **Observation** : bucket 75-89 → BUY_NO winrate 72.7%, BUY_YES 29.2% (pattern typique de biais positif + sycophancy)
- **Hypothèse** : LLM déclare BUY_YES sur cas marginaux qui devraient être UNCLEAR, et garde BUY_NO aux cas flagrants
- **Tests à mener** (3, en shadow, sans modifier prod) :
  1. Prompt neutre (ordre randomisé, pas d'exposition de la direction naturelle)
  2. Prompt inversé (reformule "supporte-t-il NO ?") → contrôle de framing
  3. Multi-model consensus (Claude Haiku + Mistral en parallèle sur 200 events)
- **Fix** : table `llm_shadow_results`, variants `impact_analyzer_v2_neutral.py` + `_v2_inverted.py`, feature flag `llm_shadow_experiments_enabled`
- **Chantier 4 du prompt d'audit**

### 2.2 🟡 Dépendance OpenAI unique
- **Problème** : pas de fallback LLM. Si GPT-4o down, pipeline bloqué. Pas de circuit breaker
- **Fix** : abstraction LLM provider avec fallback Claude/Mistral
- **Ticket séparé**, non-bloquant pour collecte

### 2.3 🔵 Pas de validation des excerpts en prod
- **Note** : validation client-side existe (substring exact), mais pas de métrique sur taux de rejet LLM pour excerpts invalides. À exposer dans dashboard admin

---

## 3. Risques légaux & réglementaires

### 3.1 🔴 Statut Polymarket en France
- **Contexte** : bloqué par l'ANJ fin 2024, accessible VPN → zone grise
- **Implication** : un site FR qui route des ordres peut tomber sous ANJ (intermédiaire pari) ou AMF (PSI / CIF)
- **Builder program ≠ cover réglementaire** : il donne droit côté Polymarket, pas côté FR
- **Action** : audit légal fintech FR (avocat spécialisé, ~3-5k€), **avant lancement public**

### 3.2 🔴 Absence CGU + mentions légales + disclaimers
- Pas de CGU
- Pas de mentions légales
- Pas de politique de risque claire
- Pas de disclaimer "perte totale possible" sur onboarding
- **Action** : rédaction + validation avocat

### 3.3 🟠 Pas de tracking des pertes utilisateur
- **Problème** : pas de cooling-off, pas de limite de mise, pas de self-exclusion
- **Impact** : exposition éthique + potentiellement légale (devoir d'information)
- **Fix prévu** dans le pivot "Learn & Trade" :
  - `user_limits` (budget_weekly_eur, max_stake_eur, cooloff_until)
  - BudgetBar sticky dans header
  - CooloffModal après 3 pertes consécutives
  - Age gate 18+

### 3.4 🟡 Quota daily signaux = limite marketing, pas risque
- Le quota actuel est une limite produit (free tier), pas une protection contre le surtrading

---

## 4. Corrections techniques — top 15 (impact / coût)

Issu de la section 1.5 de l'audit externe. Reclassé ici avec statut.

| # | Correction | Impact | Coût | Chantier | Statut |
|---|---|---|---|---|---|
| 1 | Aligner `clustering_cosine_threshold` doc ↔ code | 5 | 1 | 1 | 🔴 À faire |
| 2 | `min_articles_per_event` 1→2 + `min_unique_sources_per_event=2` | 4 | 1 | 2 | 🔴 À faire |
| 3 | Remplacer simhash par near-dup embeddings (cosine ≥0.95) | 5 | 2 | 2 | 🔴 À faire |
| 4 | Ajouter 3 baselines sur `signal_outcomes` + calcul parallèle | 5 | 2 | 3 | 🔴 À faire |
| 5 | Prompt `impact_analyzer` v2 neutre (shadow) | 4 | 2 | 4 | 🟠 À faire |
| 6 | Multi-model consensus (Claude Haiku en second avis, shadow) | 4 | 2 | 4 | 🟠 À faire |
| 7 | Retirer/repositionner `OrderForm` | 5 | 3 | Pivot produit | 🟠 En décision |
| 8 | `baseline_winrate_*` dans `signal_outcomes` (comparaison continue) | 4 | 2 | 3 | 🟠 À faire |
| 9 | Audit réglementaire (avocat fintech FR) | 5 | 3 | Externe | 🟠 À planifier |
| 10 | Abstraction LLM provider (fallback Claude/Mistral) | 3 | 2 | Ticket séparé | 🟡 Backlog |
| 11 | Filtre liquidité min 10k$ sur signaux broadcastés | 3 | 1 | Post-collecte | 🟡 Backlog |
| 12 | Feature flags + A/B framework minimaliste | 4 | 3 | Post-collecte | 🟡 Backlog |
| 13 | Logger 9 rejection reasons avec % distribution + dashboard | 3 | 2 | 5 | 🟡 À faire |
| 14 | Worker concurrency >1 sur queues `pipeline` / `scoring` | 2 | 1 | — | 🔵 Backlog |
| 15 | Redis pub/sub WebSocket `/ws/signals` (scale >1 pod) | 2 | 3 | — | 🔵 Backlog |

---

## 5. Risques techniques non-critiques (observabilité)

### 5.1 🟡 Pas de rate limiting côté Polymarket API
- Risque de bannissement IP si un worker part en boucle

### 5.2 🟡 Pas de circuit breaker sur LLM
- Si GPT-4o down → pipeline bloqué sans fail-fast

### 5.3 🟡 Simhash collision non détectée
- Si 2 articles réellement différents ont le même simhash, silencieusement ignorés (cf. 1.1)

### 5.4 🟡 Divergences config doc/code non monitorées
- Pas de test d'intégrité BLUEPRINT.md ↔ `config.py` (cf. 1.3)
- Fix : Chantier 1 prévoit un test CI

### 5.5 🔵 WebSocket mono-pod
- `/ws/signals` ne scale pas au-delà d'1 instance (pas de pub/sub Redis)

### 5.6 🔵 Container `/app/signal/` shadowait stdlib `signal`
- **Résolu** pendant la session (dirs stales supprimés du volume Docker)

---

## 6. Risques scientifiques & méthodologiques

### 6.1 🟠 `signal_score` = combinaison linéaire à poids arbitraires
- Poids 0.75 / 0.25 et sous-poids jamais validés sur held-out set
- Pas de backtesting rigoureux
- **Action post-collecte** : valider les poids actuels contre données J0-J10, identifier ceux à tuner

### 6.2 🟠 Pas de test de stationnarité
- Le marché change. Modèle qui marche avril peut ne pas marcher juillet
- **Action** : après J+10, refaire tourner audit à J+30 et comparer distributions

### 6.3 🟡 Pas de held-out set pour validation
- Tout le dataset historique sert au diagnostic → risque overfit sur l'audit lui-même

---

## 7. Issues frontend / UX

### 7.1 🟠 OrderForm 25KB — composant le plus lourd
- À refactorer dans le pivot "Learn & Trade" vers version simplifiée (slider 1-10€, pas input libre)

### 7.2 🟡 Signal score dans l'UI
- Nom actuel suggère action recommandée. Dans contexte éducatif, renommer `interest_score` ou `catalyst_strength` en UI (calcul backend inchangé)

### 7.3 🟡 Landing par défaut = Homepage marketing
- Dans le pivot : landing par défaut après login = `/apprendre`, pas `/signals`

### 7.4 🟡 Onboarding actuel = 4 questions profil
- Dans le pivot : ajouter tutoriel 5 paper trades obligatoires + quiz risque 3 questions avant premier trade réel

### 7.5 🔵 Task 23 (Playwright E2E) reportée
- Plan Axis-A l'avait prévue, Playwright non installé
- Backlog

---

## 8. Dette DB & migration

### 8.1 🟡 Users existants sans `user_limits`
- Pivot "Learn & Trade" créera la table → backfill nécessaire (budget_weekly_eur défaut 20€, quiz_passed=false)
- Forcer quiz avant prochain trade réel

### 8.2 🟡 Pas de champ `dedup_method` sur `news_clean`
- Chantier 2 prévoit migration pour tracer quoi a filtré quoi

### 8.3 🟡 Pas de colonnes baseline sur `signal_outcomes`
- Chantier 3 prévoit migration (6 nouvelles colonnes)

### 8.4 🔵 Pas de table `llm_shadow_results`
- Chantier 4 prévoit création

---

## 9. Plan de collecte 10 jours

### 9.1 Pré-requis avant de relancer la pipeline
- [ ] Chantier 1 : alignement config
- [ ] Chantier 2 : durcir clustering
- [ ] Chantier 3 : baselines tracking
- [ ] Vérifier que les 4 captures outcomes (T+5m/15m/1h/24h) sont actives
- [ ] Vérifier que `check_resolved_markets` tourne (cron 6h)
- [ ] Gel du code scoring/LLM/seuils — aucune modif

### 9.2 Métriques à logger par signal (rappel)
Par signal généré :
1. `signal_score` actuel
2. `baseline_random_direction` (seeded par signal.id)
3. `baseline_momentum` (delta ≥2% sur 30 dernières minutes)
4. `baseline_multi_source` (≥2 tier-1 sur entité dans 2h)
5. Pour chaque : `move_t5min`, `move_t15min`, `move_t1h`, `move_t24h`, `correct`

### 9.3 Critères go/no-go J+10
Par direction (YES/NO) × bucket (55-64, 65-74, 75-89, 90+) :
- n ≥ 30 par cellule sinon collecter +10j
- Winrate + IC95
- Edge vs meilleure baseline (en points de %)
- Expected value assumant spread moyen

**Décisions possibles** :
- Edge > baseline ≥5pp avec p<0.05 → pipeline marche, passer au tuning
- Edge ≤ baseline → pipeline décoratif, rebuild depuis prompts
- n insuffisant → +10 jours collecte

---

## 10. Ce qui N'EST PAS dans le backlog (hors scope volontaire)

- Refonte scoring / nouveaux features / LightGBM — **attendre J+10**
- Modification des prompts de prod — **gel 10 jours**
- Abstraction LLM provider — ticket séparé, non-bloquant
- Scaling WebSocket multi-pods — non-critique à ce stade
- Concurrence Celery >1 — non-critique
- Décision finale pivot éducation/trading — **décidée** (Learn & Trade, plan à rédiger)
- Audit légal approfondi — externe, avocat

---

## 11. Ordre d'exécution recommandé

### Immédiat (cette semaine)
1. **Rédiger** plan pivot `2026-04-23-pivot-learn-and-trade.md`
2. **Lancer** Chantier 1 du prompt d'audit (alignement config)
3. **Contacter** un avocat fintech FR pour devis audit légal

### Semaine 2
4. Chantier 2 (clustering durcissement)
5. Chantier 3 (baselines)
6. Vérifier pipeline + captures outcomes
7. **Relancer pipeline** avec code gelé + nouveaux logs

### Semaine 2 → 3 (collecte J0→J10)
8. Laisser tourner, code gelé
9. Chantier 5 en parallèle (dashboard admin)
10. Démarrer implémentation pivot Learn & Trade (indépendant de la collecte)

### J+10
11. Analyse dashboard admin (baselines, IC95, p-values)
12. Décision go/no-go sur tuning scoring
13. Chantier 4 (shadow LLM bias) sur 48h si go sur tuning

### Pré-lancement public
14. CGU + mentions légales + age gate + disclaimers
15. Retour audit légal + corrections
16. Pivot Learn & Trade complet en prod

---

**Dernière mise à jour** : 2026-04-23
**Sources** :
- Conversation Claude Code audit session (24 tâches Axis-A, audit précision)
- Audit externe utilisateur (Partie 1 : 5 trous + 15 corrections + risques)
- Décisions produit session (pivot Learn & Trade, caveat builder program)
