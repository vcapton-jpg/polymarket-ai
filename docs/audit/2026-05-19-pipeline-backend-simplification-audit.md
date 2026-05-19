# Audit Fluidité Pipeline + Backend Foresight — 2026-05-19

> Audit read-only A-à-Z. 5 agents spécialisés en parallèle (flux pipeline,
> backend/données, complexité/défauts, architecture, infra/SRE+sonde live) +
> synthèse. **Diagnostic only — aucun code modifié, aucune PR, aucune mutation prod.**
> Spec : `docs/superpowers/specs/2026-05-19-pipeline-backend-audit-design.md`.
> Plan : `docs/superpowers/plans/2026-05-19-pipeline-backend-audit-execution.md`.

## Résumé exécutif

**Verdict global : la non-fluidité bout-en-bout n'est pas un problème de code de
pipeline — c'est une CRISE MÉMOIRE ACTIVE en production.** Une chaîne causale
unique explique le ressenti "le site rame" :

> Gaspillage de calcul (95 % d'events singletons scorés pour rien + REINDEX HNSW
> à chaque batch + thrash Redis) → charge CPU/RAM → contre une config Docker
> **sur-allouée à 224 %** (17 GB committed sur 7,6 GB utilisables) → **18 OOM-kills
> en ~129 min** → workers tués en plein traitement → latence API 3–4 s, signaux
> retardés/perdus, DB à 243 % CPU. Et **Sentry est éteint** donc tout ça est
> invisible jusqu'à la plainte utilisateur.

**Top 5 leviers de fluidité (chiffrés) :**

1. **Right-sizing mémoire Docker** — committed 17 GB vs 7,6 GB usable, host à
   143 MB free / swap 93 %, 18 OOM-kills/2 h. Le levier #1, effet immédiat.
2. **Stopper le `REINDEX INDEX CONCURRENTLY` HNSW à chaque batch d'embeddings**
   — 51,9 % du temps DB total, moyenne 213 s, + 3 GB d'index fantômes INVALID.
3. **Gater les events singletons hors du scoring temps réel** — ~3000/j paient
   2 embeddings OpenAI + vector-search pgvector pour 0 signal (95 % `no_candidates`).
4. **Câbler Sentry** (`SENTRY_DSN` vide, code déjà prêt #98) — quick-win
   observabilité : les 18 OOM n'ont déclenché aucune alerte.
5. **Déployer le fix #128 seul** (deep-links Polymarket 404 user-facing) en
   cherry-pick — sans embarquer le delta trading #126/#127 (money-switch).

La grande majorité de la dette **structurelle** (god-functions, sprawl de flags,
2 paths de signal divergents) est réelle mais **gelée par le PLAN_30D en vol** —
classée P2 / "à NE PAS faire maintenant".

---

## Findings par domaine

### A — Flux pipeline & orchestration

- **[A-F01] 95 % des events sont des singletons qui paient toute la chaîne
  scoring pour 0 signal** — high / effort M / impact high. Preuve : psql prod
  `pct_singleton=97.7 events_24h=3239 ; no_candidates=3088 / scoring_done=103` ;
  `_try_instant_event_async` (`app/workers/tasks_pipeline.py:310`) →
  `run_hybrid_search` (`:425`) exécute 2 embeddings + hybrid search **avant** de
  conclure `no_candidates` (`tasks_scoring.py:737-756`). Conflit : **oui** —
  même zone que le chantier clustering T-022 (PLAN_30D) → à coordonner.
- **[A-F02] Boucle de re-scoring ~5× / event** — high / M / high. Preuve : logs
  worker-scoring 60 min → 672 `run_hybrid_search` pour ~135 events/h ;
  `retry_stuck_events` (`tasks_scoring.py:1233-1258`, 300 s) +
  `rescore_zero_signal_events` (`:1294-1330`, 600 s) redispatchent `no_candidates`
  / déjà-scorés. Conflit : non (pure orchestration, `skip_llm` réutilise le cache).
- **[A-F03] Code mort confirmé prod** — med / S / med. `signal_pending_reasoning`
  = **0 rows** (psql) ; `backfill_reasoning` + queue partielle inerte ;
  `run_llm_impact` / `compute_score_and_signal` = wrappers zéro-appelant. Conflit : non.
- **[A-F04] Double-dispatch `try_instant_event`** (process_article + batch),
  inerte mais fragile — low / S / low. `tasks_pipeline.py:164` + `:498`,
  `unlinked_embedded_24h=0`. Conflit : non.
- **[A-F05] `_check_simhash_dup` : scan Python O(500)/article** — low / M / low.
  `tasks_pipeline.py:687-701`, 3420×/j. Conflit : interagit avec clustering → coordonner.
- **Correction d'une note d'audit périmée** : `simple_clusterer.py` **n'est PAS
  code mort** — utilisé par `_build_events_async` (`tasks_pipeline.py:531-584`,
  sweep backfill). L'audit 2026-05-10 disait l'inverse → mémoire corrigée.

### B — Backend / API & données

- **[B-F1] `REINDEX INDEX CONCURRENTLY` HNSW (2,3 GB) après chaque batch
  d'embeddings + 3 GB d'index INVALID** — high / M / high. Preuve :
  `app/workers/tasks_ingestion.py:283-289` ; `pg_stat_statements` : 16 calls,
  **51,9 % du temps DB**, moyenne **213 609 ms** ; `\d markets` →
  `idx_..._ccnew` (1390 MB) + `_ccnew1` (1630 MB) INVALID, `idx_scan=0`. Conflit : non.
- **[B-F2] SELECT ORM `Market` full-column (2× vector 1536) en hot path** —
  high / M / high. `pg_stat_statements` : **1,31 M calls**, 17,6 % du temps DB ;
  call-sites `tasks_scoring.py:788,916`, `tasks_outcomes.py:48,322`,
  `tasks_sourcing.py:80`. Fix : `load_only()` excluant `embedding*`/
  `market_retrieval_text`. Conflit : non.
- **[B-F3] Bloat & churn `markets` (66 737 dead tuples, 22 %, 10 GB)** — med / M
  / med. `pg_stat_user_tables` ; 5 variantes `UPDATE markets SET …` cumulant
  >21 % du temps DB ; table jamais émondée (307k lignes / ~1409 actifs). Conflit : non.
- **[B-F4] Redis à 100 % de maxmemory, éviction LRU permanente** — high / S /
  high. `redis-cli INFO memory` : `used 1023.82M / max 1.00G`, volatile-lru ;
  db0 = 58 586 clés. Cache-miss embeddings → re-calls OpenAI. Conflit : non.
- **[B-F5] Surface API très large, peu consommée par le front** — low / M / low.
  `app/api/main.py:139-205` ~24 routers ; front n'en type que ~5. Conflit :
  **partiel** (trading/polymarket_signing = chantier P2/P3) → observation only.

### C — Complexité, code mort & défauts

- **[C-F03] `UnboundLocalError` latent sur `y` (T-LIQUID / LEVIER-1)** — **high**
  / S / high. `app/signal/signal_builder.py:203-295` : `y` assignée l.205 dans
  `if yes_p is not None and direction in (...)` mais lue l.295 hors de ce bloc
  (`market_price=y if yes_p is not None else 0.0`) → exception avalée par le
  `except` worker, signal perdu sans trace si `yes_p is None` + catégorie
  blacklistée. Fix défensif (n'altère pas le filtrage). Conflit : non — **mais
  toucher signal_builder pendant la mesure des gates = défensif STRICT only**.
- **[C-F01] Path async `build_signal`/`_persist_signal` mort en prod (151 LOC)**
  — med / S / high. `signal_builder.py:508-658`, seul appelant =
  `_backfill_reasoning_async` (rescue sans beat depuis 2026-04-27). Conflit : non.
- **[C-F02] Cluster `backfill_reasoning` + `SignalPendingReasoning` +
  `reasoning_analyzer.py` quasi-mort (~320 LOC)** — low / M / med. Conflit : non
  (Agent A a confirmé `signal_pending_reasoning` vide en prod).
- **[C-F04] `tasks_scoring.py` god-module 1 581 lignes (4 responsabilités)** —
  med / M / med. Conflit : non (refactor pur).
- **[C-F05] `compute_score_and_signal` legacy task = dead code dans le registre
  Celery** — low / S / low. `tasks_scoring.py:1194-1197`. Conflit : non.
- **[C-F06] Sprawl de feature-flags `config.py` (634 lignes, 6 ensembles)** —
  low / L / med. Conflit : **oui** — flags T-001/T-013/LEVIER-1/2 en vol.

### D — Architecture & frontières

- **[D-F01] `SignalBuilder.build_signal` god-function 349 lignes (filtres +
  scoring + DTO + dispatch shadow)** — high / M / high.
  `signal_builder.py:152-501`. Fix : chaîne de `FilterRule` itérable. Conflit :
  **non au sens structurel mais geler** (gates mesurés par PLAN_30D sprint 2-3).
- **[D-F02] Dépendance de couche inversée `signal/` → `workers/`** — high / S /
  high. `signal_builder.py:32-61` importe `workers.tasks_shadow…apply_async` →
  tests unitaires de la chaîne de filtres dépendants de Celery/Redis. Fix :
  injecter `rejection_sink` callable. Conflit : non.
- **[D-F03] Deux paths de construction de Signal divergents (même fichier,
  scores calculés différemment)** — high / M / high. `:508-658` vs `:147-501`.
  Conflit : non (legacy non-actif).
- **[D-F04] Config monolithique 28 flags sans groupement ni validation
  master→threshold** — med / M / med. Conflit : non (mais ne pas toucher les
  défauts en vol).
- **[D-F05] Attributs privés (`_score_label`…) sur le modèle ORM `Signal` comme
  transport** — med / S / med. `signal_builder.py:491-500` ↔
  `tasks_scoring.py:1107-1115`. Fix : dataclass `SignalBuildResult`. Conflit : non.
- **[D-F06] Mutation de domaine dans l'orchestrateur (Filter B/E inline dans
  `tasks_scoring`)** — med / M / med. Conflit : non.

### E — Infra / SRE / observabilité / live

- **[E-F01] Oversubscription mémoire 224 % → OOM-kills en boucle** — **high / M
  / high**. Σ limites compose = **17,00 GB** vs `free -m` 7745 total / **143
  free, swap 1911/2047** ; `dmesg | grep -c oom-kill:` = **18** (1 / ~7 min) ;
  restarts worker-markets 18, scoring-1 9, pipeline-1 8. Conflit : non.
- **[E-F02] Latence /api/health 2,8–4,3 s, /api/signals 0,47→3,0 s (var 6×)** —
  high / M / high. `curl -w` prod ; symptôme direct de F01. Conflit : non.
- **[E-F03] Sentry DARK — cécité totale erreurs prod** — high / S / med.
  `SENTRY_DSN length=0` ; code câblé #98 ; 18 OOM = 0 alerte. Conflit : non.
- **[E-F04] Écart déploiement : fix #128 (deep-links 404 user-facing) non
  déployé** — med / S / med. prod `38813b3` (#125) vs origin/main +4
  (#126 P2b, #127 bridge, **#128**, #129). Conflit : **partiel** — ne livrer
  que #128 (cherry-pick), pas le bundle trading.
- **[E-F05] Redis au plafond exact + fragmentation 0,04 (swap-out OS)** — med /
  S / med. Corrélé F01. Conflit : non.
- **[E-F06] Posture hôte : `.env:` / `foresight.env` parasites, ports
  3000/8001 en 0.0.0.0** — low / S / low. UFW actif, Caddy+CF devant. Conflit : non.
- **[E-F07] CI sans tests d'intégration ni gate de déploiement** — low / M /
  low. `.github/workflows/ci.yml` = ruff + smoke + `pytest -m "not integration"`.
  Conflit : non.

---

## Roadmap priorisée

P0 = effet fluidité fort, risque faible, sans conflit PLAN_30D, actionnable vite.
P1 = fort impact mais effort/coordination. P2 = gros chantier ou gelé PLAN_30D.

| ID | P | Finding | Pourquoi ça nuit à la fluidité | Esquisse fix | Effort | Impact | Risque | Conflit PLAN_30D ? |
|---|---|---|---|---|---|---|---|---|
| R1 | **P0** | E-F01 oversubscription mémoire 224 % | OOM-kills 1/7 min → workers tués, latence 3–4 s, DB 243 % CPU | replicas worker-ingestion/scoring 2→1, limites 3G→1.5G pour Σ<7G, `--max-tasks-per-child` | M | high | moyen (infra, hors logique signal) | non |
| R2 | **P0** | B-F1 REINDEX HNSW/batch + 3 GB index INVALID | 51,9 % du temps DB, 213 s/run, bloat markets | reindex nightly conditionnel (pas par batch) ; drop des `_ccnew` INVALID (hors audit) | M | high | faible (HNSW incrémental) | non |
| R3 | **P0** | E-F03 Sentry dark | crashs/OOM invisibles, pas de MTTR | renseigner `SENTRY_DSN` (code prêt) | S | med | nul | non |
| R4 | **P0** | A-F02 boucle re-scoring ~5×/event | hybrid-search répété pur déchet → charge inutile | borner redispatch (compteur/`last_seen`), exclure `no_candidates` de `rescore_zero` | M | high | faible | non |
| R5 | **P0** | C-F03 UnboundLocalError latent `y` | signal silencieusement perdu (except avalé) | `y = float(yes_p) if yes_p is not None else None` tôt ; fix STRICTEMENT défensif | S | med | faible (à prouver no-behavior-change) | non* |
| R6 | **P0** | E-F04 fix #128 non déployé | clic "voir sur Polymarket" = 404 user-facing | cherry-pick **#128 seul**, pas le bundle trading | S | med | faible | partiel (isoler #128) |
| R7 | **P1** | A-F01 singletons scorés pour rien (95 %) | ~3000/j de machinerie lourde pour 0 signal | court-circuit avant `run_hybrid_search` si singleton mono-source | M | high | moyen | **oui — coordonner T-022** |
| R8 | **P1** | B-F2 SELECT Market full-column (2×vec 1536) | 17,6 % temps DB, I/O inutile ×1,3 M | `load_only()` hors `embedding*`/retrieval_text | M | high | faible | non |
| R9 | **P1** | A-F03+C-F01+C-F02+C-F05 code mort (~470 LOC) | dette/bruit, piège pour contributeurs | supprimer path async + backfill_reasoning + wrappers (psql vide confirmé) | M | med | faible | non |
| R10 | **P1** | B-F4/E-F05 Redis 100 % maxmemory | éviction → re-calls OpenAI, latence scoring | après R1 : auditer préfixes, ajuster TTL/maxmemory | S | med | faible | non |
| R11 | **P1** | D-F02 dépendance inversée signal→workers | tests unitaires filtres dépendants Celery/Redis | injecter `rejection_sink` callable | S | med | faible | non |
| R12 | **P1** | E-F07 CI sans intégration ni gate deploy | régressions DB/Redis passent ; deploy manuel | service PG+Redis en CI ; script deploy idempotent | M | med | faible | non |
| R13 | **P2** | B-F3 bloat/churn `markets` | autovacuum permanent sur 10 GB | grouper UPDATE prix/liq ; table `market_quotes` (migration) | M | med | moyen | non |
| R14 | **P2** | D-F01/F05/F06+C-F04 god-functions & transport privé | maintenabilité, diffs larges | filter-pipeline, `SignalBuildResult`, split tasks_scoring | L | med | élevé | **oui — gelé sprint 2-3** |
| R15 | **P2** | C-F06/D-F04 sprawl flags config | coût cognitif, dépendances cachées | sous-`BaseSettings` par gate + validation | L | med | moyen | **oui — flags en vol** |
| R16 | **P2** | A-F05 `_check_simhash_dup` O(500) Python | hot-path ingestion sous burst | borne temporelle / `bit_count` SQL | M | low | faible | coordonner clustering |

\* R5 : pas de conflit logique, mais toute édition de `signal_builder.py` pendant
la mesure des gates PLAN_30D doit être **purement défensive** et vérifiée
non-impactante sur les décisions de filtrage avant merge.

---

## À NE PAS faire

- **Ne pas `git pull` tout le delta origin/main en prod** — entremêle #126/#127
  (bridge trading lié au money-switch OFF). Cherry-pick **#128 seul**.
- **Ne pas augmenter Redis maxmemory ni les limites Docker à chaud** — aggrave
  le swap host (E-F01). Réduire l'empreinte d'abord (R1 avant R10).
- **Ne pas remplacer NullPool par un pool** (`app/db/database.py:20-43`) —
  décision anti-OOM documentée (incident 2026-05-05).
- **Ne pas modifier la logique/seuils de clustering ni
  `_try_instant_event_async`** — cœur du chantier T-022 (PLAN_30D). R7 = gater
  *autour*, en coordination, pas recâbler.
- **Ne pas supprimer `simple_clusterer.py`** — vivant (sweep `build_events`) ;
  la note d'audit 2026-05-10 était fausse.
- **Ne pas fusionner `try_instant_event` dans `process_article`** — l'isolation
  de queue `pipeline`→`scoring` est volontaire (anti head-of-line blocking).
- **Ne pas toucher les flags PLAN_30D** (`IMPACT_PROMPT_VERSION=v2`,
  `ENABLE_MAX_SPREAD_FILTER`, `ENABLE_LLM_RECALIBRATION`) ni l'ordre/seuils des
  gates, ni les défauts dans `config.py` — mesure en vol.
- **Ne pas refactorer la god-function/le sprawl de flags avant stabilisation
  PLAN_30D sprint 3** (R14/R15 gelés).
- **Ne pas droper les routers `trading`/`polymarket_signing`/`agents`** —
  intégration P2/P3 active (#125-129), money-switch OFF par conception.
- **Ne rien réécrire/nettoyer en prod** — cet audit est read-only ; R1-R16 sont
  des recommandations, l'implémentation est une phase 2 à autoriser séparément.

---

## Méthodo & limites

- 5 sous-agents read-only en parallèle (general-purpose ×3 avec SSH Tailscale
  read-only, code-reviewer, code-architect), 2026-05-19. Synthèse thread principal.
- Contrat de sûreté HARD respecté : aucune mutation prod, aucun secret imprimé,
  findings sourcés `fichier:ligne` et/ou commande prod + extrait.
- État au moment de l'audit : prod `38813b3` (#125), **4 commits derrière**
  origin/main ; flags v2 / LEVIER-1 / LEVIER-2 ON, T-001 OFF, money-switch OFF.
- Limites : pas de panel web Hetzner (host via SSH only, par décision) ; pas
  d'audit sécu applicatif type CSO ; chiffres prod = instantané (1 run), à
  re-mesurer avant action ; le bloat `markets` (B-F3) et la cause de la fuite
  RSS workers (E-F01) mériteraient un profilage dédié.
- **L'OOM (E-F01) est un incident ACTIF** au moment de l'audit, pas seulement
  une dette : à traiter en priorité dans une phase 2 d'implémentation autorisée.
