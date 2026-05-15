# Plan 30 jours — Qualité Signal Foresight

> **Source de truth** pour le chantier "Faire passer le RTP de −1.88% à ≥ +5%".
> Référence cross-session : tout Claude futur DOIT lire ce fichier avant d'agir.
> Last updated : 2026-05-11 par flotte d'agents (audit 6 axes ML/Latency/Scoring/LLM/Sources/Clustering + meta-audit Architecture).

---

## 0. CONTEXTE — état du système au 2026-05-11

### 0.1 Métriques actuelles (30 jours)

| Métrique | Valeur | Note |
|---|---|---|
| Signaux émis 30j | 725 | ~24/jour |
| Signaux résolus T+1h | 698 (96%) | 27 unresolved (selection bias négligeable, 4%) |
| Ties (move = 0) T+1h | 38 (5.4%) | Actuellement comptés comme losses → biais |
| **Winrate naïf** | 46.33% | Incorrect — inclut ties comme losses |
| **Winrate corrigé** (excl. ties) | **48.96%** | **CI95% [45.19, 52.74]** — 50% est dans le CI → indistinct du coin flip |
| RTP T+1h | **−1.88%** (t = −0.63) | **Non statistiquement significatif** |
| Brier(score/100) | 0.291 | Pire qu'un constant (0.249) → score anti-corrélé |
| avg(score/100) vs base_rate | 0.669 vs 0.47 | Biais surconfiance +20pp |
| 99.5% signaux mono-article | 694/698 | Clustering cassé → LLM jamais nourri en multi-source |

### 0.2 Patterns RTP par bucket (T+1h, 30j)

**Direction × prix marché** (BUY_NO catastrophique sur prix bas) :
```
BUY_NO  × prix<0.30  : n=211, move avg +17.1%, RTP catastrophique
BUY_NO  × prix 0.40-0.50 : n=24,  75% wr, RTP +5.86%   ✓
BUY_NO  × prix 0.20-0.30 : n=68,  50% wr, RTP −39%     ⚠️
BUY_NO  × prix 0.80+     : n=39,  28% wr, RTP −5.19%   ❌
BUY_YES × prix<0.20      : n=77,  39% wr, RTP +26.55%  ✓✓
BUY_YES × prix 0.30-0.40 : n=34,  50% wr, RTP +13.42%  ✓✓
BUY_YES × prix 0.40-0.60 : n=40,  42% wr, RTP −5%      ❌
```

**Sources** (n ≥ 9) :
```
Top alpha :
 X @Reuters         : n=25, RTP +21.68%
 X: @WatcherGuru    : n=7,  RTP +104% (anecdotal mais signal_rate 8.3% = sélectif)
 The Hill           : n=26, RTP +5.41%
 NYT Politics       : n=5,  RTP +19.3%

Sources toxiques (à kill) :
 X: @FirstSquawk         : n=60, RTP −13.95%
 Middle East Eye         : n=27, RTP −12.79%
 Guardian World          : n=9,  RTP −76.90%
 Reuters World via Google: n=12, RTP −25.20%
 X @Polymarket           : n=8,  RTP −20.95%
```

**Score bucket** :
```
80-84 : n=16,  RTP +23.47% (anecdotal, CI ±25pp)
75-79 : n=67,  RTP +1.32%
65-74 : n=336, RTP −5.3%   ❌ 48% du volume, perdant
<65   : n=274, RTP −0.32%  (some leak below threshold ?)
```

**Cosine** :
```
0.65-0.70 : n=110, RTP +4.82% ✓
0.50-0.55 : n=115, RTP +6.98% ✓ (contre-intuitif, à investiguer)
0.55-0.60 : n=218, RTP −11.42% ❌ 32% volume, le pire
```

### 0.3 Bugs structurels confirmés

1. **`prompts/impact_analysis_v1.txt:49-52`** — le `market_yes_price` n'est JAMAIS passé au LLM. Faute #1.
2. **`app/workers/tasks_pipeline.py:248`** — `_try_instant_event_async` filtre `EventNewsLink.id.is_(None)` → ne merge JAMAIS dans event existant. 3178 paires mergeables détectées sur 30j.
3. **`app/signal/direction_eval.py:11`** — `up = new > base` strict (pas `>=`) → ties asymétriques entre BUY_YES (loss) et BUY_NO (win).
4. **`app/workers/tasks_outcomes.py`** — capture `get_price_yes` (best-bid YES), pas mid-price → biais asymétrique structurel.
5. **`signal_reasoning_v1.txt` path async = MORT** : `event_news_links.key_excerpt` NULL sur 100%, `llm_model_version` NULL sur 725/725 signaux. La validation anti-hallucination ne tourne JAMAIS.
6. **`X @Reuters` vs `X: @Reuters`** (et 4 autres paires) = doublons en DB → analytics pollués.
7. **Bonus breaking-news ACTIVEMENT NÉFASTE** : <30min → RTP −3.31% (devrait être +). Le +5/+2.5/+1 pousse les mauvais signaux dans des buckets de score plus haut.
8. **Bonus multi-source INERTE** : 99.5% signaux à 1 article → ne s'active jamais.
9. **Pas de CI GitHub Actions** — 120+ tests existent mais ne tournent à aucun PR.
10. **Sentry pas câblé** (vérifié, aucun `import sentry_sdk` actif).

### 0.4 Décisions de conception non négociables

- **Préserver la prod live** pendant les changements. Pas de big-bang.
- **Une seule mutation par sprint** sur le pipeline live. Reste en shadow.
- **Mesure avant action** : tout fix testé en backtest harness AVANT deploy.
- **N minimum 200** pour qu'un finding soit exploitable (Wilson CI demi-largeur ≤ 7pp).

---

## 1. OBJECTIFS 30 JOURS

| Métrique | Baseline (J0) | Cible (J+30) |
|---|---|---|
| RTP T+1h | −1.88% (non-sig) | **≥ +5%** (significatif au CI95) |
| Winrate corrigé T+1h | 48.96% [45.19, 52.74] | **≥ 53%** [≥ 50.5 borne basse CI95] |
| Volume signaux/jour | ~24 | ≥ 30 |
| % events non-singleton | 2.4% | ≥ 20% |
| CI vert sur main | 0% | 100% |
| Sentry events live | 0 | Actif |

---

## 2. SPRINT 1 — Semaine 1 (J0-J7) : FONDATIONS MESURE + QUICK WIN

**Objectif unique** : Avoir une mesure propre + 1 levier shippé.
**Success criterion** : RTP rolling 7j visible en dashboard live + CI vert + harness backtest fonctionnel reproductible sur 30j.

### Tâches

#### T-001 [P0] — DROP `BUY_NO × market_price<0.30` dans signal_builder
- **Owner** : Claude
- **Effort** : 1h dev + 1h validation backtest
- **Critère acceptation** :
  - Backtest sur 30j historique : RTP global passe de −1.85% à ≥ +3% sur n_retenu ≥ 480
  - Gardé derrière feature flag `ENABLE_DIR_PRICE_FILTER` (default true)
  - Logue chaque rejet avec raison
- **Fichiers** : `app/signal/signal_builder.py`, `app/core/config.py` (flag)
- **Dépendances** : T-005 (backtest harness)
- **Risque** : aucun, défense pure (n'émet pas de bad signals)

#### T-002 [P0] — Fix tie handling dans direction_eval.py
- **Owner** : Claude
- **Effort** : 2h
- **Critère** :
  - `direction_correct` retourne `None` quand `new == base` (3-tier)
  - `winrate` agrégé exclut explicitement les ties (`WHERE direction_correct IS TRUE` ou `IS FALSE`, pas `IS NULL`)
  - Update endpoint `/api/admin/stats/extended` pour rapporter `n_ties` séparément
- **Fichiers** : `app/signal/direction_eval.py`, `app/api/routes/admin_stats.py`
- **Impact** : winrate rapporté 46.33% → 48.96%

#### T-003 [P0] — Wilson CI95 sur tous les findings agrégés
- **Owner** : Claude
- **Effort** : 1h
- **Critère** : endpoint admin retourne `ci_low_95` et `ci_high_95` sur chaque bucket. Buckets `n<50` marqués `"reliability": "anecdotal"`.
- **Fichiers** : `app/api/routes/admin_stats.py`

#### T-004 [P0] — CI GitHub Actions
- **Owner** : Claude (push), Utilisateur (Settings → Branches → required check)
- **Effort** : 2h
- **Critère** :
  - `.github/workflows/ci.yml` avec : `pytest tests/unit -x --maxfail=5`, `ruff check app/`, `python -c "from app.api.main import app"` (smoke import)
  - Required check sur `main`
  - 1 PR test fait passer le CI green
- **Fichiers** : `.github/workflows/ci.yml`

#### T-005 [P0] — Backtest harness reproductible
- **Owner** : Claude
- **Effort** : 1 jour
- **Critère** :
  - `scripts/backtest/replay.py` : CLI prenant `--rule <module>` + `--window-days N`
  - Charge `signals + signal_outcomes` depuis prod DB (via `ssh foresight psql`)
  - Applique la rule, calcule : winrate, RTP, Brier, retention, n_kept, by_bucket, CI95
  - Output JSON + table markdown
  - Rules définies dans `scripts/backtest/rules/{baseline.py, dirprice_filter.py, threshold75.py, lr_v1.py}`
- **Fichiers** : `scripts/backtest/replay.py`, `scripts/backtest/rules/*.py`
- **Note** : standalone Python, pas dans le pipeline (read-only sur prod DB)

#### T-006 [P0] — Sentry SDK
- **Owner** : Claude
- **Effort** : 1 jour
- **Critère** :
  - `pip add sentry-sdk[fastapi]`
  - Init dans `app/api/main.py` (lifespan) + workers Celery (`app/workers/celery_app.py`)
  - Variable env `SENTRY_DSN` dans `.env`
  - Test : `raise Exception("sentry test")` visible dans Sentry UI dashboard
- **Fichiers** : `pyproject.toml`, `app/api/main.py`, `app/workers/celery_app.py`, `.env.example`
- **Note** : free tier Sentry suffisant (5k events/mois)

#### T-007 [P0] — Désactiver 5 sources toxiques + dédup paires source_name
- **Owner** : Claude (SQL direct via SSH Tailscale)
- **Effort** : 30 min
- **Critère** :
  - `UPDATE sources_registry SET active=false WHERE source_name IN ('X: @FirstSquawk', 'Middle East Eye', 'Guardian World', 'Reuters World via Google', 'X @Polymarket')`
  - Détection paires doublons (`X @Reuters` vs `X: @Reuters`, idem AFP, AP, DeItaone) : merger en fusionnant `news.source_id` (garder la plus active)
  - Documenter dans `sources_registry.notes`
- **Risque** : perte de volume signaux ~10-15% — acceptable car compensé par fix #1

#### T-008 [P0] — Cost watch OpenAI (alerte si dérive)
- **Owner** : Claude
- **Effort** : 4h
- **Critère** :
  - Task `app/workers/tasks_ops/check_openai_usage.py` quotidienne (beat 06:00 UTC)
  - Fetch `https://api.openai.com/v1/usage` (ou alt : agrégat local des appels logués)
  - Si `daily_cost > settings.llm_cost_alert_usd` → Telegram bot alert
- **Fichiers** : `app/workers/tasks_ops/check_openai_usage.py`, `app/workers/celery_app.py` (beat entry)

### Sprint 1 — Critères de validation

- [ ] CI vert sur 1 PR test (T-004)
- [ ] `python -m scripts.backtest.replay --rule rules.baseline --window-days 30` retourne les chiffres baseline (T-005)
- [ ] Sentry montre au moins 1 event test (T-006)
- [ ] `grep ADMIN /opt/foresight/.env` post-T-001 deploy montre `ENABLE_DIR_PRICE_FILTER=true`
- [ ] `curl /api/admin/stats/extended` montre `ci_low_95` et `ci_high_95` partout (T-003)
- [ ] `n_ties` séparé du `wins/losses` dans l'agrégat (T-002)
- [ ] J+7 : RTP rolling 7j visible et meilleure que J0

---

## 3. SPRINT 2 — Semaine 2 (J7-J14) : PRIX-CONDITIONNALITÉ DANS LE LLM

**Objectif** : Le LLM voit enfin le prix et ne mise plus à contre-marché sans edge.
**Success criterion** : BUY_NO RTP > −3% sur 7j post-deploy (vs −10.2% baseline).

### Tâches

#### T-009 [P0] — `prompts/impact_analysis_v2.txt`
- **Owner** : Claude
- **Effort** : 4h (write + 1h review)
- **Critère** :
  - INPUT : ajoute `market_yes_price` et `market_category`
  - TASK : `Recommend a direction ONLY IF estimated true_prob differs from market_yes_price by ≥ 0.10. Otherwise NEUTRAL.`
  - Payoff-awareness explicite : `BUY_NO at p<0.20 → tail bet 0.20 reward vs 0.80 loss. DO NOT recommend unless edge ≥ 0.15.`
  - OUTPUT : ajoute `true_prob_estimate`, `expected_move_pct_1h`, `edge_vs_market`
  - Few-shots symétriques (1 YES, 1 NO, 1 NEUTRAL)

#### T-010 [P0] — Caller `app/llm/impact_analyzer.py` update
- **Owner** : Claude
- **Effort** : 2h
- **Critère** :
  - Signature : `analyze_impact(event_text, market_question, market_yes_price, market_category)`
  - Tous les call-sites updated (`signal_builder.py`)
  - Compatibilité backward : si `OPENAI_IMPACT_PROMPT_VERSION=v1` → use v1, sinon v2 (default v2 post-deploy)
- **Fichiers** : `app/llm/impact_analyzer.py`, `app/signal/signal_builder.py`, `app/core/config.py`

#### T-011 [P0] — Hard filter post-LLM (defense-in-depth)
- **Owner** : Claude
- **Effort** : 1h
- **Critère** : dans `signal_builder.py` après réception réponse LLM :
  ```python
  edge = llm_analysis.get("edge_vs_market", 0)
  if direction == "BUY_NO" and yes_price < 0.20 and edge < 0.15: return None
  if direction == "BUY_YES" and yes_price > 0.80 and edge > -0.15: return None
  ```
- **Note** : indépendant du LLM (le filter T-001 + ceci = double sécurité)

#### T-012 [P1] — Logger `llm_model_version` sur chaque signal
- **Owner** : Claude
- **Effort** : 1h
- **Critère** : `Signal.llm_model_version` populé sur 100% des nouveaux signaux (vs 0% actuel)
- **Fichiers** : `app/signal/signal_builder.py`

#### T-013 [P1] — Investiguer pourquoi path async LLM mort
- **Owner** : Claude (investigation)
- **Effort** : 1 jour
- **Critère** : document dans BLUEPRINT §11 pourquoi `signal_reasoning_v1.txt` ne tourne pas et soit re-active soit supprime
- **Risque** : double-écriture signaux si on l'active naïvement → mesurer en shadow d'abord

### Sprint 2 — Critères de validation

- [ ] `prompts/impact_analysis_v2.txt` mergé
- [ ] Shadow deploy 24h : RTP par bucket prix × direction visible dans `/admin/stats/extended`
- [ ] BUY_NO × prix<0.20 et BUY_YES × prix>0.80 → réduction n de ≥ 60%
- [ ] J+14 : BUY_NO RTP global > −3%

---

## 4. SPRINT 3 — Semaine 3 (J14-J21) : SCORING V2 + SOURCE QUALITY

**Objectif** : Refondre la formule scoring avec multiplicateurs direction × prix + source quality lookup.
**Success criterion** : RTP global > +3% sur 7j, volume ≥ 30/jour.

### Tâches

#### T-014 [P0] — Scoring v2 en shadow
- **Owner** : Claude
- **Effort** : 1.5 jour
- **Critère** :
  - Nouveau fichier `app/scoring/scorer_v2.py` (pur, mêmes inputs que v1)
  - Alembic migration : column `signal_score_v2` Numeric(5,1) nullable sur `signals`
  - `signal_builder.py` écrit AUSSI `signal_score_v2` (mais le gate d'emit reste sur v1)
  - Pas d'impact runtime sur prod
- **Fichiers** : `app/scoring/scorer_v2.py`, `app/scoring/weights_v2.py`, `alembic/versions/<new>_signal_score_v2.py`, `app/signal/signal_builder.py`

#### T-015 [P0] — Formule v2 (composants ré-équilibrés)
- **Owner** : Claude
- **Effort** : intégré T-014
- **Critère** : implémenter selon agent Scoring v2 :
  - Supprimer bonus breaking-news (-3.31% RTP confirmé)
  - Supprimer bonus multi-source (inerte tant que clustering pas fixé — réactivé après T-022)
  - `confirmation` weight 0.15 → 0.05
  - `llm_combined` weight 0.60 → 0.65
  - `cosine_score_calibrated` ajouté à strength (poids 0.20)
  - `trade_quality` weight 0.25 → 0.20
  - Investigate `trade_quality` anti-corrélé : peut-être l'inverser franchement post-shadow

#### T-016 [P0] — Direction × prix multiplier table
- **Owner** : Claude
- **Effort** : intégré T-014
- **Critère** : table de modulateurs appliquée comme multiplicateur final du score
  ```python
  DIR_PRICE_MULTIPLIER = {
    ("BUY_YES", "<0.20"): 1.30,
    ("BUY_YES", "0.30-0.40"): 1.20,
    ("BUY_YES", "0.50-0.60"): 0.60,
    ("BUY_NO", "0.40-0.50"): 1.15,
    ("BUY_NO", "0.20-0.30"): 0.30,
    ("BUY_NO", ">0.70"): 0.50,
    # défaut 1.00
  }
  ```

#### T-017 [P0] — Source quality lookup + cron
- **Owner** : Claude
- **Effort** : 4h
- **Critère** :
  - Alembic : column `sources_registry.rolling_rtp_30d` Numeric(5,2) nullable
  - Cron quotidien `app/workers/tasks_ops/update_source_quality.py` : pour chaque source active, compute rolling RTP 30j, write to DB
  - `scorer_v2` lit `rolling_rtp_30d` via cache mémoire (refresh 5 min) et map vers multiplicateur ∈ [0.5, 1.30]
- **Fichiers** : `app/workers/tasks_ops/update_source_quality.py`, `app/scoring/scorer_v2.py`, alembic migration

#### T-018 [P0] — Endpoint comparaison v1 vs v2
- **Owner** : Claude
- **Effort** : 2h
- **Critère** : `GET /api/admin/scoring/compare?window=7d` retourne pour chaque signal récent : (v1_score, v2_score, direction, market_price, source, move_t1h_pct, RTP). Aussi métriques globales : retain_rate, RTP_v1, RTP_v2, Brier_v1, Brier_v2.

#### T-019 [P0] — Decision flip v1 → v2
- **Owner** : Claude + validation Utilisateur
- **Effort** : 30 min (décision basée sur data)
- **Critère** : Si RTP shadow v2 sur 7j ≥ RTP v1 + 5pp avec IC95 non-overlapping → flip emit gate sur `signal_score_v2`. Garde v1 calculé encore 30j pour rollback.

#### T-020 [P1] — Mid-price capture dans outcomes
- **Owner** : Claude
- **Effort** : 4h
- **Critère** :
  - Alembic : add `price_t5min_mid`, `price_t15min_mid`, `price_t1h_mid`, `price_t24h_mid` nullable
  - `tasks_outcomes._capture_price_async` : appelle `clob.enrich_market()` au lieu de `get_price_yes()`, calcule `(best_bid + best_ask) / 2` si dispo, fallback `last_trade_price`
  - Documenter discontinuité historique dans BLUEPRINT (pas de backfill possible)

#### T-021 [P2] — Ajouter 5 sources gratuites manquantes
- **Owner** : Claude
- **Effort** : 1h
- **Critère** : ajout dans `seed_sources.py` + curl validation 200 OK depuis Hetzner :
  - The Block (crypto institutionnel)
  - TechCrunch (tech/IA earnings)
  - ABC News Politics (élections 2026)
  - RealClearPolitics (polling aggregator)
  - The Verge (tech)

### Sprint 3 — Critères de validation

- [ ] `signal_score_v2` populé sur 100% nouveaux signaux 24h post-deploy shadow
- [ ] `/api/admin/scoring/compare?window=7d` retourne JSON valide
- [ ] J+21 : décision flip v1→v2 prise et appliquée si critères atteints
- [ ] J+21 : RTP global > +3% (cible sprint atteinte)

---

## 5. SPRINT 4 — Semaine 4 (J21-J30) : CLUSTERING + ML CALIBRATION + REFACTORS

**Objectif** : Fixer la fragmentation events + activer bonus multi-source + LR calibrated comme overlay.
**Success criterion** : Singletons < 80% (vs 97.6%), RTP > +5%, Direction enum livré, paths async investigated.

### Tâches

#### T-022 [P0] — Fix fragmentation `_try_instant_event_async`
- **Owner** : Claude
- **Effort** : 1 jour
- **Critère** :
  - Avant de créer un new event, query :
    ```sql
    SELECT id FROM events
    WHERE last_seen >= NOW() - INTERVAL '90 minutes'
      AND bucket = $1
      AND embedding <=> $2 < 0.22  -- cosine sim ≥ 0.78
    ORDER BY embedding <=> $2 ASC
    LIMIT 5;
    ```
  - Si match ET intersection `key_entities` ≥ 1 → ajoute `EventNewsLink(role="supporting")` + update `last_seen`, `articles_count`, `key_entities`
  - Sinon → create new event (comportement actuel)
  - Test unit : 2 news same topic 5min apart → merge dans 1 event
- **Fichiers** : `app/workers/tasks_pipeline.py:248`
- **Risque** : faux positifs (2 events distincts qui se ressemblent) → seuil strict 0.78 + entities = mitigé

#### T-023 [P0] — Re-activate bonus multi-source dans scorer_v2
- **Owner** : Claude
- **Effort** : 30 min
- **Dépendance** : T-022 doit être déployé et avoir produit ≥ 50 multi-source events
- **Critère** : re-introduit dans `scorer_v2` avec poids modeste (+2 si n=2, +4 si n≥3), validé par shadow

#### T-024 [P1] — Logistic Regression calibrated (overlay)
- **Owner** : Claude
- **Effort** : 1 jour
- **Critère** :
  - Train script `scripts/ml/train_lr_calibrated.py` :
    - Load `signals + signal_outcomes`, target = `signed_move_t1h > 0`
    - Features : direction_binary, market_yes_price, dir × price interaction, signal_score (v2), log1p(latency_min), source_quality_quantile
    - LogisticRegression L2 + IsotonicRegression calibration (CV time-aware, 5-fold)
    - Save model pickle in `models/lr_v1.pkl`
  - Inference dans `signal_builder.py` : compute `predicted_prob_win`, stocker dans `signal_predictions(variant='lr_v1')`
  - Threshold émission ≥ 0.55 (configurable)
- **Fichiers** : `scripts/ml/train_lr_calibrated.py`, `app/signal/signal_builder.py`, `models/lr_v1.pkl`
- **Note** : SHADOW only au début, pas de gate emit

#### T-025 [P1] — Direction enum refactor
- **Owner** : Claude
- **Effort** : 4h
- **Critère** :
  - `app/core/types.py` : `class Direction(StrEnum): BUY_YES = "BUY_YES"; BUY_NO = "BUY_NO"; NEUTRAL = "NEUTRAL"`
  - Migrate les 90 call-sites (grep `"BUY_YES"\|"YES"\|"UP"`)
  - Test backward compat : accept "YES"/"BUY_YES"/"UP" en input mais normalise en `Direction.BUY_YES`
- **Fichiers** : `app/core/types.py`, ~30 fichiers

#### T-026 [P1] — Schema invariant test au CI
- **Owner** : Claude
- **Effort** : 1h
- **Critère** : `tests/unit/test_schema_invariants.py` :
  - `from app.db.models import *` (smoke import)
  - Assert toutes tables ont `__tablename__`, PK définie
  - Assert pas de drift INTEGER/BIGINT (lessons from #73 simhash bug)

#### T-027 [P2] — Supprimer code mort `simple_clusterer.py`
- **Owner** : Claude
- **Effort** : 30 min
- **Critère** : `git rm app/event_engine/simple_clusterer.py` + retirer imports orphans. 177 LOC nettoyés.

### Sprint 4 — Critères de validation

- [ ] % events ≥ 2 articles passe de 2.4% à ≥ 10% sur 7j post-T-022
- [ ] LR_v1 shadow Brier < 0.27 (vs 0.291 baseline)
- [ ] J+30 : RTP global ≥ +5% sur 7j rolling, IC95 borne basse ≥ 0%
- [ ] `Direction` enum déployé sans casser tests existants

---

## 6. BACKLOG POST-30J (P2/P3, à arbitrer)

| ID | Tâche | Trigger |
|---|---|---|
| T-028 | A/B GPT-4o vs GPT-4o-mini | Si BUY_NO RTP < 0 après Sprint 2 |
| T-029 | LightGBM avec interactions non-linéaires | Quand n_résolus ≥ 2000 (~3 mois supplémentaires) |
| T-030 | Telegram MTProto via proxy résidentiel ($30-100/mo) | Décision business |
| T-031 | Source × category matrix avec auto-désactivation | Après T-017 stabilisé |
| T-032 | Twitter API v2 Basic ($200/mo) | Si Telegram pivot |
| T-033 | Backfill rétroactif clustering (controversé) | À débattre |
| T-034 | Symmetric few-shots Iran-style équilibrés | Post-Sprint 2 prompt v2 |
| T-035 | Dashboard live RTP par bucket | Post-Sentry + observabilité |
| T-036 | Audit security (.env secrets en clair sur VPS) | À planifier |
| T-037 | Concurrency dedupe race condition (UNIQUE constraint) | Risque faible mais à fixer |

---

## 7. RISQUES GLOBAUX & MITIGATIONS

| # | Risque | Probabilité | Mitigation |
|---|---|---|---|
| R1 | **Sur-filtration** : volume effondre, IC95 trop large pour mesurer | Élevée | UNE mutation par sprint, le reste en shadow |
| R2 | **Survivor bias temporel** : les buckets toxiques redeviennent profitables | Moyenne | Re-run backtest hebdo, alerte si bucket exclu repasse RTP > 0 sur 7j |
| R3 | **Sample size étroit** : findings n<50 peuvent être bruit | Élevée | Tout finding tagged `"reliability": "anecdotal"` si CI95 demi-largeur > 7pp |
| R4 | **Drift schéma** (INTEGER/BIGINT type drift) | Moyenne | Schema invariant test au CI (T-026) |
| R5 | **Secrets en clair dans .env** | — | Audit security séparé (T-036) |
| R6 | **LLM cost dérive** | Faible | T-008 cost watch |
| R7 | **Telegram MTProto bloqué sur Hetzner** | Confirmé | Source non utilisable sans proxy résidentiel — accepté |

---

## 8. COMMANDES UTILES (référence)

### SSH (via Tailscale)
```bash
ssh foresight                                   # alias dans ~/.ssh/config → 100.78.45.84
ssh foresight "<command>"                       # one-shot
```

### Base de données
```bash
# Query SQL sans entrer dans le container
ssh foresight "docker compose -f /opt/foresight/docker-compose.yml exec -T db psql -U postgres -d signal -c 'SQL'"

# Shell SQL interactif
ssh foresight -t "docker compose -f /opt/foresight/docker-compose.yml exec db psql -U postgres signal"
```

### Logs
```bash
ssh foresight "docker compose -f /opt/foresight/docker-compose.yml logs --tail=100 worker-ingestion"
ssh foresight "docker compose -f /opt/foresight/docker-compose.yml logs --since=10m app"
```

### Restart (préfère restart à force-recreate sauf changement .env ou volumes)
```bash
ssh foresight "cd /opt/foresight && docker compose restart app worker-ingestion beat"
ssh foresight "cd /opt/foresight && docker compose up -d --force-recreate app"   # si .env changé
```

### Endpoint admin stats (ADMIN_TOKEN dans .env du VPS)
```bash
curl -s -H "X-Admin-Token: $(ssh foresight 'grep ^ADMIN_TOKEN /opt/foresight/.env | cut -d= -f2-')" \
  "https://yourforesight.com/api/admin/stats/extended" | python3 -m json.tool
```

### Backtest harness (Sprint 1)
```bash
python -m scripts.backtest.replay --rule rules.baseline --window-days 30
python -m scripts.backtest.replay --rule rules.dirprice_filter --window-days 30
```

---

## 9. JOURNAL D'AVANCEMENT

| Date | Action | Résultat |
|---|---|---|
| 2026-05-10 | Audit 7-agents initial (PR-flotte) | Findings biais BUY_YES, fragmentation 97.6%, Redis OOM zombie |
| 2026-05-10 | 4 PRs hotfix prod (#74-77) | Pipeline ressuscité, 1500+ articles/24h |
| 2026-05-10 | PR #76 Redis volatile-lru | Plus jamais d'OOM zombie |
| 2026-05-10 | PRs #78-92 Telegram setup | Telegram MTProto bloqué par Hetzner anti-fraud → désactivé |
| 2026-05-11 | Endpoint `/api/admin/stats/extended` | Métriques RTP/winrate/etc. par bucket |
| 2026-05-11 | Audit 6-agents v2 (avec data RTP) | Plan 30j (ce fichier) |
| 2026-05-11 | **PLAN_30D_SIGNAL_QUALITY.md créé** | Plan complet, traçable, cross-session |
| 2026-05-11 | T-002 + T-003 — tri-state tie + Wilson CI95 (PR #94) | `direction_correct_3state` → None on ties, ties exclus du winrate ; CI95 sur tous les buckets de `/admin/stats/extended` |
| 2026-05-11 | T-005 — backtest harness (PR #95) | `scripts/backtest/replay.py` read-only ; règles `baseline.py` + `dirprice_filter.py` ; rapport markdown + JSON ; tourne en docker container `app` |
| 2026-05-11 | T-001 — drop BUY_NO × YES<0.30 (PR #96) | Filtre en prod via `enable_buyno_lowprice_filter` + `buyno_lowprice_filter_threshold=0.30` ; **backtest 30j: RTP −1.91 % → +4.68 %**, retention 86 % |
| 2026-05-11 | T-007 — désact 5 sources toxiques + dédup 6 paires `source_name` | SQL direct VPS : 1 291 `news.source_id` migrées (139+49+13+22+6+1 062) ; 6 orphans + 5 sources toxiques `is_active=false` |
| 2026-05-11 | T-004 — CI GitHub Actions (PR #97) | Workflow `lint + unit tests` : ruff (autofix legacy 690/745, ignore 22 règles cosmétiques), smoke imports FastAPI+Celery, pytest unit (`-m "not integration"`), schema-models import. Auto-marker dans `tests/conftest.py` skipe les tests DB-bound. **446 tests passent en CI ; 54 deselected.** |
| 2026-05-11 | T-006 — Sentry SDK câblé (PR #98) | `app/core/sentry_init.py` partagé, idempotent, no-op sans `SENTRY_DSN`. Intégrations FastAPI + Starlette + Celery + SQLAlchemy. `traces_sample_rate=0.05` (≈6k spans/h, sous free-tier). PII désactivé par défaut. Roundtrip Sentry vérifié avec fake DSN. |
| 2026-05-11 | T-008 — daily OpenAI cost watch (PR #99) | `app/workers/tasks_costs.py:emit_daily_cost` beat task (24h cadence, queue=default). Log greppable `openai.cost.daily` + alerte Telegram quand 24h ≥ 50% de `llm_cost_alert_usd`. 5 unit tests, no-DB. |
| ✅ J7 | **Sprint 1 complet — fondations + filtre T-001 live** | 7 PRs (#94→#99), 451 tests verts, CI baseline en place, observabilité câblée. **Prochaine étape: laisser tourner 7j et mesurer RTP réel post-filtre.** |
| 2026-05-11 | T-011 — fix `llm_model_version` propagation (PR #101) | Migration 032 ajoute la colonne sur `event_market_analysis` ; writer + builder propagent jusqu'au `Signal` ; `/admin/stats/extended` gagne `by_llm_model_version` avec Wilson CI95. Avant : 732/732 NULL. Après : chaque nouveau signal stamp `gpt-4o-mini@<version>`. |
| 2026-05-11 | T-009 — prompt v2 price-conditional (PR #102) | `prompts/impact_analysis_v2.txt` + machinerie toggle via `IMPACT_PROMPT_VERSION` (default v1). `ImpactAnalyzer._model` suffixed `@v1`/`@v2` pour split admin stats. Reasoning forcé au format `"Market at X, my estimate Y, so Z."`. 6 unit tests + script offline `compare_impact_v1_v2.py`. Toggle OFF par défaut. |
| 2026-05-11 | T-009 replay offline (PR #103) | Run sur 50 events réels (14 j) : **agreement v1↔v2 = 74-76 %**, désaccords concentrés sur YES<0.20 (toxic zone). v2 plus prudent, anchoring explicite au prix. GO for flip. |
| 2026-05-11 22:08 UTC | **🚀 Flip `IMPACT_PROMPT_VERSION=v2` sur prod** | Premier signal v2 émis à 22:10 UTC : `event 2121, BUY_YES @ market=0.64, implied_yes=0.80 → edge +16 pp`. Worker booté en v2 confirmé via `_model='gpt-4o-mini@v2'`. Snapshot pré-flip dans `docs/measurements/post_T001_pre_v2flip_2026-05-12.json`. |
| 2026-05-11 | Health-check rollout v2 (PR #104) | `scripts/shadow/check_v2_rollout.py` : exit 2 si winrate v2 < 40 % sur n≥30 OU error rate > 5 %. Bonus : fix d'un bug latent dans `_reset_cost_state_for_tests` (`fetched_at_monotonic=0.0` cassait sur fresh CI interpreter, désormais `float("-inf")`). |
| 2026-05-12 | T-013 candidat — BUY_NO × YES≥0.70 (PR #105) | Exploration data 30 j : BUY_NO bleeds globally (n=380, RTP −10.24 %) ; mirror de T-001 identifié → BUY_NO × YES≥0.70 n=70 RTP −4.6 %. Backtest T-001+T-013 : RTP +6.42 %, retention 60 %, t=1.82 (~93 %). **Toggle OFF** — décision flip/no-flip à H+168 selon que v2 a déjà neutralisé le pattern. Audit complet dans `docs/measurements/buyno_band_exploration_2026-05-12.md`. |
| 2026-05-12 | Realistic backtest + Shadow capture + T-LIQUID + T-DATA (PR #109-112) | `realistic_replay.py` (entry@ask + spread + exit dynamique) : RTP proxy −1.75 % → réaliste **−10 %**. `shadow_signals` capture les rejets pour ML + validation live des filtres. T-LIQUID blacklist catégorie (Hezbollah/Iran Ceasefire, −5 pp RTP retiré). T-DATA capture `spread_at_signal` + `implied_yes_probability`. |
| **2026-05-13** | **🔻 T-001 DÉSACTIVÉ (data-driven)** | Shadow capture sur **n=162 rejets** montre `rtp_avoided = +2.28 %` : T-001 rejetait des signaux légèrement **profitables** dans le régime post-v2 (l'audit historique du 11/05 disait −17 % — régime changé car v2 filtre déjà les BUY_NO toxiques upstream). `ENABLE_BUYNO_LOWPRICE_FILTER=false` sur prod. Reversible. **Le shadow capture a prouvé sa valeur : sans lui on aurait gardé un filtre nocif.** |
| 2026-05-13 | Point indicateurs ~H+36 v2 | Global 30j : winrate 50.0 %, RTP proxy −2.09 %. v2 (n=156) : winrate 51.3 %, RTP −1.96 % vs legacy 49.5 %/−2.13 % — amélioration **non-significative** (CI95 [43,59]). Volume ×2 via T-022a (24→45/j). Edge **non prouvé** — cohérent verdict VC-Killer. Vrai blocker = spread (proxy −2 % → réaliste −10 %). |
| ⬜ J14 (2026-05-18) | **H+168 v2 — décider flip T-013 + valider T-001-off** | `check_v2_rollout.py --hours 168` (besoin n≥250 v2 pour significativité). Re-check shadow `rtp_avoided` T-001 sur n élargi. Décider flip T-013 selon que v2 a neutralisé `BUY_NO × YES≥0.70`. |
| ⬜ Next | Spread gate (`signal_max_spread_pp`) — le levier transformateur restant | Backtest projette +3-5 pp RTP réel. Indépendant de v2/T-013/T-022. À implémenter dès que T-DATA a 7j de données de spread pour calibrer le seuil. |
| ⬜ J21 | Validation Sprint 3 (scoring v2 + source quality) | — |
| ⬜ J30 | Validation Sprint 4 + bilan | — |

---

## 10. RÈGLES D'ENGAGEMENT POUR CLAUDE

> Tout Claude qui reprend ce projet DOIT respecter ces règles.

1. **Lire ce fichier en premier** avant toute action. Idem `memory/project_current_state.md`.
2. **Ne JAMAIS** sauter de tâche au profit d'une autre sans validation Utilisateur explicite.
3. **Marquer chaque tâche terminée** dans le journal d'avancement (§9) avec un commit dédié.
4. **Toute mutation prod** passe par PR + merge sur main, jamais commit direct.
5. **Toute tâche Sprint S+N** attend la validation du Sprint S avant démarrage.
6. **Si une cible Sprint n'est pas atteinte** à la deadline → analyse cause + replan, ne sautent pas au sprint suivant.
7. **Backtest harness obligatoire** avant tout changement scoring/filter émission.
8. **Wilson CI95 obligatoire** sur tout chiffre rapporté à l'Utilisateur.
9. **Pas de nouveaux deps Python** sans inscription dans pyproject.toml + uv lock.
10. **Sentry events doivent être actifs** dès Sprint 1 fin — sinon stop tout et le câbler.
