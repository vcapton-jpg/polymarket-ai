# Audit Fluidité Pipeline + Backend — Plan d'Exécution

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to run this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Note d'adaptation :** ce plan exécute un **audit read-only** (pas du code TDD). Les "tâches" sont des étapes d'orchestration d'agents + synthèse. Pas de tests unitaires : la "vérification" de chaque tâche = critère d'acceptation explicite.

**Goal:** Produire `docs/audit/2026-05-19-pipeline-backend-simplification-audit.md` — findings priorisés + roadmap P0/P1/P2 pour simplifier/optimiser/fluidifier la pipeline et le backend Foresight, en read-only strict.

**Architecture:** 5 sous-agents read-only dispatchés en parallèle (1 message, 5 Agent calls), chacun avec brief verbatim self-contained (CONTEXTE + CONTRAT SÛRETÉ + bloc domaine). Le thread principal collecte, synthétise, écrit le livrable, met à jour la mémoire. Aucun code modifié, aucune mutation prod.

**Tech Stack:** Agent tool (subagent_type general-purpose & code-reviewer & code-architect), `ssh foresight` (Tailscale, read-only), skill `browse`/`gstack` (sonde HTTP publique).

Spec source : `docs/superpowers/specs/2026-05-19-pipeline-backend-audit-design.md`.

---

## File Structure

- **Create (par le thread principal, Task 4)** : `docs/audit/2026-05-19-pipeline-backend-simplification-audit.md` — le livrable unique.
- **Modify (Task 5)** : mémoire projet `~/.claude/projects/-Users-vadim-polymarket-ai/memory/project_current_state.md` (+ nouvelle entrée pointeur audit).
- **Aucun fichier repo/app modifié.** Audit pur read-only.
- Ce plan : `docs/superpowers/plans/2026-05-19-pipeline-backend-audit-execution.md`.

---

## Blocs réutilisables (assemblage verbatim)

> Règle d'assemblage non ambiguë : le prompt de CHAQUE agent (Task 2) =
> `CONTEXTE_PARTAGÉ` (verbatim) + `CONTRAT_SÛRETÉ` (verbatim) + le bloc domaine de l'agent.
> Tout copier-coller intégral. Ne rien résumer.

### CONTEXTE_PARTAGÉ (verbatim dans chaque agent)

```
Tu es un agent d'audit READ-ONLY sur le projet Foresight (alias Polymarket AI).

PRODUIT : plateforme temps réel qui détecte les news rendant un marché Polymarket
"wrong" et émet un signal actionnable. Boucle : News (RSS/X/RSSHub) → clustering
événements → matching marchés Polymarket → LLM (gpt-4o-mini) → scoring heuristique
→ signal → outcomes T+5m/15m/1h/24h.

STACK : Python 3.11 + FastAPI + Celery + Postgres 16 + pgvector + Redis +
React/Vite. Docker Compose ~15 conteneurs. Hôte : Hetzner CPX32 (4 vCPU, 8 GB
RAM usable ~7.6 GB). Repo racine = le worktree courant. Backend dans app/
(api, workers, signal, scoring, llm, event_engine, ingestion, trading, db, core).
Référence technique exhaustive : BLUEPRINT.md (FR, dense). Docs : docs/.
Plan qualité-signal ACTIF et à NE PAS contredire : docs/PLAN_30D_SIGNAL_QUALITY.md.

ÉTAT PROD VÉRIFIÉ 2026-05-19 (à confirmer toi-même, peut bouger) :
- Prod /opt/foresight = commit 38813b3 (#125), 4 commits derrière origin/main
  (#126 P2b, #127 P3 bridge, #128 fix deep-links 404, #129 modals).
- Flags .env : IMPACT_PROMPT_VERSION=v2 ; ENABLE_BUYNO_LOWPRICE_FILTER=false ;
  ENABLE_MAX_SPREAD_FILTER=true (LEVIER-1) ; ENABLE_LLM_RECALIBRATION=true
  (LEVIER-2) ; SENTRY_DSN vide (Sentry câblé mais dark) ; money-switch OFF
  (BUILDER_PRIVATE_KEY/ENABLE_NATIVE_RELAYER_ONBOARDING/ENABLE_RELAYER_DEPLOY unset).
- ~37 signaux/24h. RTP proxy t1h ≈ −2 % ; BUY_NO ≈ −10.5 % / BUY_YES ≈ +8.8 %.
- Issues structurelles relevées par audits antérieurs (À VÉRIFIER, file:line
  possiblement périmés — ne pas citer sans re-vérifier) : ~97 % events
  singletons ; _try_instant_event_async ne merge jamais dans event existant ;
  simple_clusterer.py = code mort ; path LLM reasoning async possiblement mort ;
  bonus breaking-news/multi-source inertes ou néfastes.

ACCÈS PROD : `ssh foresight "<cmd>"` (alias ~/.ssh/config, tunnel Tailscale).
Projet sur le VPS dans /opt/foresight. DB : container `db`,
`docker compose -f /opt/foresight/docker-compose.yml exec -T db psql -U postgres -d signal -c "SELECT ..."`.

ANGLE DE L'AUDIT : « le plus FLUIDE possible » — goulots, latence, hops
redondants, code mort, complexité accidentelle, sprawl de config, fragilité
opérationnelle. PAS le winrate/RTP du signal en soi (périmètre PLAN_30D) — sauf
là où la complexité de la machinerie nuit à la fluidité.
```

### CONTRAT_SÛRETÉ (verbatim dans chaque agent — prod proche-argent)

```
CONTRAT DE SÛRETÉ — STRICTEMENT READ-ONLY. Violation = échec de la tâche.

- REPO : lecture / grep / glob uniquement. AUCUN Edit/Write sur le code app.
- PROD via `ssh foresight` : autorisé UNIQUEMENT :
  * SQL `SELECT` only. JAMAIS UPDATE/DELETE/INSERT/ALTER/DROP/TRUNCATE/CREATE.
  * `docker compose ps|logs|stats|config|top`, `git log|status|rev-parse|diff`,
    `df|free|ss|uptime|cat|ls|grep|systemctl status`, `redis-cli INFO|DBSIZE|
    --scan` (lecture). 
  * DENYLIST ABSOLUE : aucun restart/up/recreate/stop/down, aucun `alembic`,
    aucune écriture Redis (SET/DEL/FLUSHALL/EXPIRE), aucun git pull/push/checkout/
    fetch, aucune écriture .env ou fichier, aucune commande de mutation, aucun
    `docker exec` qui écrit.
- SECRETS : ne JAMAIS imprimer une valeur de .env. Présence/longueur seulement
  (`grep -c`, `${#v}`, masquage). Pas de tokens/clés/passwords en sortie.
- yourforesight.com : GET/HEAD publics uniquement. Aucun POST, aucune action
  authentifiée, aucun login.
- FINDINGS SOURCÉS : chaque finding = `chemin/fichier:ligne` ET/OU preuve prod
  (commande exacte + extrait de sortie). Tout chiffre agrégé → Wilson CI95.
- CONSCIENCE TRAVAIL EN VOL : si une simplification entre en conflit avec
  docs/PLAN_30D_SIGNAL_QUALITY.md, le money-switch gaté, ou la discipline
  prod-vs-main → la classer "à NE PAS faire", ne pas la recommander.
- En cas de doute sur une commande : NE PAS l'exécuter, la noter comme
  "non vérifié (commande mutante évitée)".
```

### FORMAT_SORTIE_AGENT (verbatim dans chaque agent)

```
Rends EXACTEMENT cette structure markdown (≤ 1200 mots, dense, zéro blabla) :

## [Domaine X] — Findings

### Synthèse (3-5 puces)
- Les leviers de fluidité les plus importants de ton domaine, chiffrés.

### Findings détaillés
Pour chaque finding :
**[Fxx] Titre court** — Sévérité: high|med|low — Effort: S|M|L — Impact fluidité: high|med|low
- Preuve : `fichier:ligne` et/ou `commande prod` + extrait sortie
- Pourquoi ça nuit à la fluidité : 1-2 phrases
- Esquisse de fix (read-only, juste l'idée) : 1-2 phrases
- Conflit PLAN_30D / money-switch / deploy ? oui/non + lequel

### À NE PAS faire (de ton domaine)
- Pièges tentants mais en conflit avec le travail en vol.
```

---

## Task 0: Pré-vol (thread principal)

**Files:** aucun. Vérifications seulement.

- [ ] **Step 1 : Vérifier worktree propre & spec présent**

Run: `git -C /Users/vadim/polymarket-ai/.claude/worktrees/nervous-napier-42a900 status --short && ls docs/superpowers/specs/2026-05-19-pipeline-backend-audit-design.md`
Expected: spec listé ; pas de modif app non commitée inattendue.

- [ ] **Step 2 : Vérifier accès prod read-only (Tailscale)**

Run: `ssh -o ConnectTimeout=15 foresight 'cd /opt/foresight && git rev-parse --short HEAD && docker compose ps --format "{{.Name}} {{.State}}" | head -3'`
Expected: un hash court + 3 conteneurs `running`. Si échec SSH → STOP, prévenir l'utilisateur (Tailscale down).

- [ ] **Step 3 : Confirmer écart prod vs main**

Run: `ssh -o ConnectTimeout=15 foresight 'cd /opt/foresight && git fetch origin main -q 2>/dev/null; git rev-list --count HEAD..origin/main'`
Expected: un entier (≈4 attendu). Le noter pour le CONTEXTE_PARTAGÉ (mettre à jour si différent).

**Critère d'acceptation Task 0 :** SSH read-only OK, spec présent, écart prod connu.

---

## Task 1: Préparer les 5 prompts d'agent

**Files:** aucun (assemblage en mémoire de travail).

- [ ] **Step 1 : Assembler les 5 prompts**

Pour chaque agent A→E : `prompt = CONTEXTE_PARTAGÉ + "\n\n" + CONTRAT_SÛRETÉ + "\n\n" + FORMAT_SORTIE_AGENT + "\n\n" + <BLOC DOMAINE ci-dessous>`. Copier-coller verbatim, ne rien résumer. Mettre à jour dans CONTEXTE_PARTAGÉ l'écart prod-vs-main réel mesuré en Task 0.

#### BLOC DOMAINE — Agent A (subagent_type: general-purpose)

```
TON DOMAINE : FLUX PIPELINE & ORCHESTRATION.

Mission : trouver ce qui ralentit, fragilise ou complexifie inutilement la
chaîne news→signal, sans toucher la logique de signal (gel PLAN_30D).

Investigue :
1. Graphe Celery : app/workers/ (tasks_pipeline, tasks_ingestion, tasks_scoring,
   tasks_outcomes, tasks_markets, tasks_costs) + celery_app.py (beat schedule,
   queues, routing). docker-compose.yml : replicas par worker, concurrency.
2. Trace UN article de bout en bout : ingestion → dedupe → clustering
   (_try_instant_event_async dans tasks_pipeline.py) → match marché → LLM impact
   → scoring → emit signal → capture outcomes. Compte les hops, les allers-retours
   DB, les recomputes, les étapes synchrones bloquantes.
3. Preuves prod : profondeur des queues (`redis-cli -n <db> LLEN <queue>` lecture),
   cadence beat (logs), lag publish→signal p50/p95 (SQL SELECT sur signals/news
   timestamps), fréquence de restart workers (`docker compose ps` uptime + logs),
   backlog ingestion.
4. Chemins morts/dupliqués : simple_clusterer.py, path reasoning async
   (signal_reasoning), tasks beat schedulées mais inertes.
5. Idempotence/fragilité : que se passe-t-il sur retry/double-delivery ?
   race conditions dedupe ?

Livrables fluidité attendus : hops supprimables, parallélisations possibles,
code mort à retirer, étapes à fusionner — SANS changer la logique de scoring/LLM
(respecter le gel signal). Chiffre les latences.
```

#### BLOC DOMAINE — Agent B (subagent_type: general-purpose)

```
TON DOMAINE : BACKEND / API & COUCHE DONNÉES.

Investigue :
1. FastAPI : app/api/ structure, routes, endpoints morts/dupliqués, génération
   OpenAPI, drift vs frontend (frontend/src/types/api.generated.ts).
2. SQLAlchemy async : cycle de vie session, pooling (NullPool ?), patterns N+1,
   requêtes dans des boucles, manque d'await/bloquant.
3. DB : schéma, 30 migrations alembic/ (santé, migrations risquées), tables qui
   gonflent (shadow_signals, signals, news, events), index manquants sur les
   colonnes filtrées chaudes, types drift (ex. markets PK text vs id).
4. Redis : usage (cache embeddings, queues), policy mémoire, TTL, taille.
5. Preuves prod : `pg_stat_statements` si dispo (SELECT), tailles tables
   (`SELECT relname, n_live_tup ...`), index usage (`pg_stat_user_indexes`),
   `redis-cli INFO memory|keyspace`, nombre de connexions DB.

Livrables fluidité : index/req à corriger, N+1 à tuer, endpoints/schéma à
simplifier, pooling. Ne pas proposer de migration destructrice (audit only).
```

#### BLOC DOMAINE — Agent C (subagent_type: code-reviewer)

```
TON DOMAINE : COMPLEXITÉ, CODE MORT & DÉFAUTS CONCRETS (couche "warden").

Repo uniquement (pas de prod). Investigue :
1. Modules surdimensionnés / responsabilités enchevêtrées : mesure LOC + densité
   de responsabilités. Suspects connus : app/signal/signal_builder.py (empile
   gates T-001/T-LIQUID/LEVIER-1/LEVIER-2), scoring, llm/impact_analyzer.py.
2. Code mort confirmé + nouveau : simple_clusterer.py, path reasoning async,
   imports orphelins, fonctions jamais appelées, branches de flags morts.
3. Duplication (logique copiée), sprawl de feature-flags dans app/core/config.py
   (coût cognitif/maintenance).
4. DÉFAUTS CONCRETS tagués high/med/low avec fichier:ligne — bugs de correctness,
   surtout sur le chemin chaud pipeline (off-by-one, await manquant, exceptions
   avalées, états incohérents, IEEE-754/arrondis comme les fixes LEVIER récents).
   Méthodo : trace la donnée, vérifie les invariants, ne signale que ce que tu
   peux prouver par lecture.

Livrables fluidité : suppressions de code mort (LOC chiffrées), découpages de
modules, défauts à corriger classés. Marque tout conflit avec le gel signal.
```

#### BLOC DOMAINE — Agent D (subagent_type: code-architect)

```
TON DOMAINE : ARCHITECTURE & FRONTIÈRES DE MODULES.

Repo uniquement. Investigue :
1. Layering app/ (api / workers / signal / scoring / llm / event_engine /
   ingestion / trading / db / core) : dépendances, cycles, abstractions qui
   fuient, couche qui en court-circuite une autre.
2. Frontières : chaque module a-t-il une responsabilité claire et testable
   isolément ? signal_builder fait-il trop (filtres + scoring + emit + shadow) ?
   La chaîne de gates inline (T-LIQUID→LEVIER-1→LEVIER-2→…) devrait-elle être un
   pattern pipeline/registry au lieu de if imbriqués ?
3. Dette de config : config.py + sprawl de flags comme dette architecturale.
4. Simplifications structurelles "fluides" : consolidations, interfaces plus
   nettes, réduction du couplage — au service de la maintenabilité/lisibilité.

Contrainte : NE propose AUCUN refactor qui touche la logique signal en vol
(PLAN_30D) ou le money-switch. Propositions = structure, pas comportement.
```

#### BLOC DOMAINE — Agent E (subagent_type: general-purpose)

```
TON DOMAINE : INFRA / SRE / COÛT / OBSERVABILITÉ + SONDE LIVE yourforesight.com.

Investigue (prod via ssh foresight, read-only) :
1. Docker Compose : 15 services / hôte 8 GB. Resource limits/reservations,
   replicas, restart policy, healthchecks, services sur/sous-dimensionnés.
   `docker compose config`, `docker stats --no-stream`, `free -m`, OOM
   (`dmesg | grep -i oom` si lisible, `journalctl` status only).
2. Redis : policy (volatile-lru attendu), mémoire, ratio embcache.
3. Observabilité : Sentry DSN vide (câblé mais dark) → quantifie l'angle mort
   (erreurs prod invisibles) ; qualité logging ; cost-watch OpenAI (#99) actif ?
4. Écart déploiement : prod #125 vs origin/main (dont #128 fix deep-links 404
   user-facing non déployé) → risque opérationnel + process de déploiement.
5. Posture sécu hôte ÉVIDENTE seulement : secrets .env en clair (présence, pas
   valeurs), perms fichiers sensibles, fichiers parasites racine (.env: ,
   foresight.env), ports ouverts (`ss -tlnp`), firewall (`iptables -S` /
   `ufw status` si lisible), config SSH.
6. CI : .github/workflows/ci.yml — ce qui tourne, gaps, required checks.
7. SONDE LIVE yourforesight.com (skill browse/gstack OU curl, GET public only) :
   latence /api/health et /api/signals (timings réels), hash/build front servi
   vs main, erreurs console/réseau, responsivité du feed, check responsive
   rapide. Mesure la fluidité PERÇUE bout-en-bout.

Livrables : risques opérationnels, gaspillage ressources/coût, angle mort
observabilité, friction de déploiement, quick-wins infra. Sécu = uniquement
l'évident (pas un audit CSO complet).
```

**Critère d'acceptation Task 1 :** 5 prompts complets assemblés, chacun = contexte+sûreté+format+domaine, écart prod réel injecté, zéro placeholder.

---

## Task 2: Dispatch parallèle des 5 agents

**Files:** aucun.

- [ ] **Step 1 : Lancer les 5 agents en UN SEUL message**

Émettre **un seul message contenant 5 tool calls `Agent`** (parallélisme réel) :
- `Agent(description="Audit A flux pipeline", subagent_type="general-purpose", prompt=<prompt A>)`
- `Agent(description="Audit B backend/data", subagent_type="general-purpose", prompt=<prompt B>)`
- `Agent(description="Audit C complexité/défauts", subagent_type="code-reviewer", prompt=<prompt C>)`
- `Agent(description="Audit D architecture", subagent_type="code-architect", prompt=<prompt D>)`
- `Agent(description="Audit E infra/SRE/live", subagent_type="general-purpose", prompt=<prompt E>)`

Ne PAS utiliser run_in_background (on attend les 5 retours pour synthétiser).

- [ ] **Step 2 : Attendre les 5 retours**

Expected: 5 rapports markdown au FORMAT_SORTIE_AGENT.

**Critère d'acceptation Task 2 :** 5 rapports reçus.

---

## Task 3: Triage des retours (thread principal)

**Files:** aucun.

- [ ] **Step 1 : Contrôle qualité de chaque rapport**

Pour chaque rapport vérifier : (a) findings sourcés (file:line ou preuve prod),
(b) aucune violation du CONTRAT_SÛRETÉ (aucune mutation, aucun secret imprimé),
(c) angle fluidité respecté, (d) conflits PLAN_30D notés.

- [ ] **Step 2 : Re-dispatch si défaillant**

Si un agent est hors-sujet / non sourcé / a violé une contrainte : relancer CET
agent seul (Agent call unique) avec un addendum corrigeant le manquement.
Expected: rapport conforme.

**Critère d'acceptation Task 3 :** 5 rapports conformes et sourcés en main.

---

## Task 4: Synthèse & écriture du livrable (thread principal)

**Files:**
- Create: `docs/audit/2026-05-19-pipeline-backend-simplification-audit.md`

- [ ] **Step 1 : Consolider**

Fusionner les 5 rapports : dédupliquer les findings transverses, normaliser
sévérité/effort/impact, réconcilier avec docs/PLAN_30D_SIGNAL_QUALITY.md +
état LEVIER + money-switch gaté + écart prod-vs-main. Prioriser P0/P1/P2
(P0 = quick-win fluidité fort impact / faible risque ; P2 = gros chantier).

- [ ] **Step 2 : Écrire le livrable**

Structure EXACTE du fichier :
```
# Audit Fluidité Pipeline + Backend Foresight — 2026-05-19

## Résumé exécutif
- Top 5 leviers de fluidité (chiffrés, 1 ligne chacun).
- Verdict global : où est la friction principale.

## Findings par domaine
### A — Flux pipeline & orchestration
### B — Backend / API & données
### C — Complexité, code mort & défauts
### D — Architecture & frontières
### E — Infra / SRE / observabilité / live
(chaque finding sourcé : file:line ou preuve prod, sévérité, effort, impact)

## Roadmap priorisée
| ID | P | Finding | Pourquoi ça nuit à la fluidité | Esquisse fix | Effort | Impact | Risque | Conflit PLAN_30D ? |
(triée P0 → P2)

## À NE PAS faire
- Pièges tentants en conflit avec travail en vol / money-switch / gel signal.

## Méthodo & limites
- 5 agents read-only parallèles, date, écart prod-vs-main au moment de l'audit,
  Wilson CI95 sur les chiffres, ce qui n'a pas pu être vérifié.
```

Expected: fichier créé, chaque finding traçable, zéro placeholder.

**Critère d'acceptation Task 4 :** livrable écrit, structure respectée, findings sourcés, roadmap priorisée, liste "à NE PAS faire" présente.

---

## Task 5: Mise à jour mémoire & restitution

**Files:**
- Modify: `~/.claude/projects/-Users-vadim-polymarket-ai/memory/project_current_state.md` (entrée datée pointant le livrable + top findings)

- [ ] **Step 1 : Mémoire**

Ajouter un bloc daté 2026-05-19 : audit fluidité réalisé, chemin du livrable,
3-5 findings P0, et la liste "à NE PAS faire" en une ligne. Ne pas dupliquer le
livrable — juste un pointeur cross-session.

- [ ] **Step 2 : Restituer à l'utilisateur**

Résumé concis : top leviers P0, où est la friction, chemin du livrable, et
proposition de suite (implémenter P0 = phase 2 séparée, hors de cet audit).

**Critère d'acceptation Task 5 :** mémoire à jour, utilisateur informé, audit clos (diagnostic only — aucune implémentation).

---

## Self-Review (rempli par l'auteur du plan)

**1. Couverture spec :** spec §3 flotte 5 agents → Task 1/2 (briefs A-E). §4 contrat sûreté → bloc CONTRAT_SÛRETÉ verbatim dans chaque agent + Task 3 contrôle. §5 livrable structure → Task 4 Step 2 (structure exacte). §5 MAJ mémoire → Task 5. §2 décisions D1-D6 → reflétées (D3 pas de CLI warden : agent C fait la couche défauts ; D5 yourforesight.com : agent E Step 7 ; D6 Hetzner host SSH only : agent E, pas de panel web). §6 process → Task 0-5. §7 hors-scope → contraintes dans briefs. **Aucun gap.**

**2. Placeholders :** aucun "TBD/TODO". Les `<prompt A..E>` sont des références d'assemblage explicitement définies (CONTEXTE+SÛRETÉ+FORMAT+bloc domaine, tous écrits verbatim ici) — pas des placeholders vagues. `<db>`/`<queue>` dans le brief A sont des paramètres que l'agent résout en lisant celery_app.py (intentionnel, read-only).

**3. Cohérence types :** noms de blocs (CONTEXTE_PARTAGÉ / CONTRAT_SÛRETÉ / FORMAT_SORTIE_AGENT) identiques partout. subagent_type cohérents (general-purpose pour A/B/E car besoin Bash/SSH ; code-reviewer C ; code-architect D — ces 2 derniers repo-only, pas d'accès prod requis = OK). Chemin livrable identique Task 4 ↔ File Structure ↔ spec.

**Issues trouvées : aucune.**
