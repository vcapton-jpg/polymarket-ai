# Spec — Audit fluidité pipeline + backend Foresight

> Charte de l'audit A-à-Z. Source de vérité pour le plan d'exécution (skill writing-plans).
> Créé : 2026-05-19. Statut : **design approuvé par l'utilisateur, spec en revue.**

## 1. Objectif

Produire **un livrable read-only unique** : findings priorisés + roadmap concrète pour
**simplifier, optimiser et fluidifier la pipeline et le backend** de Foresight.
Diagnostic uniquement — **zéro code modifié, zéro PR, zéro mutation prod**.

Angle directeur : « le plus fluide possible ». On cherche les goulots, les hops
redondants, le code mort, la complexité accidentelle, le sprawl de config, la
fragilité opérationnelle — pas le winrate du signal (c'est le périmètre du
`docs/PLAN_30D_SIGNAL_QUALITY.md`, que cet audit doit respecter sans dupliquer).

## 2. Décisions de cadrage (verrouillées avec l'utilisateur)

| # | Décision |
|---|---|
| D1 | Combiner méthodo warden-sweep + flotte d'agents IA |
| D2 | Livrable = rapport read-only + roadmap, **zéro PR** |
| D3 | Couche « défauts concrets » via un agent code-reviewer dédié — **pas** de CLI warden installé/configuré (warden-sweep reste un outil optionnel pour une future passe correctifs) |
| D4 | Structure = **flotte parallèle par domaine + synthèse par le thread principal** |
| D5 | `yourforesight.com` **inclus** comme sonde live read-only (public, zéro credential) |
| D6 | Hetzner **hôte via SSH/Tailscale uniquement** — **pas** de panel web cloud (pas de credentials, sensible) |

## 3. Composition de la flotte

5 sous-agents read-only en **parallèle** + synthèse finale par le thread principal
(le thread principal détient le contexte projet complet — mémoire, PLAN_30D, état
prod — qu'un agent frais perdrait).

| Agent | Type subagent | Périmètre | Accès prod |
|---|---|---|---|
| **A — Flux pipeline & orchestration** | general-purpose | Celery/beat/queues, topologie workers, chaîne `news→cluster→match→LLM→score→signal→outcomes` : goulots, latence p50/p95, hops redondants, chemins morts, fragilité, idempotence | SSH read-only |
| **B — Backend / API & couche données** | general-purpose | Structure FastAPI, SQLAlchemy async (sessions/pooling), schéma & 30 migrations, requêtes chaudes / N+1 / index manquants, usage Redis, contrat API↔front (endpoints morts, drift codegen) | SSH read-only |
| **C — Complexité, code mort & défauts concrets** (remplace warden) | code-reviewer | Modules surdimensionnés / responsabilités enchevêtrées, code mort confirmé (`simple_clusterer.py`, path LLM async mort), duplication, bugs tagués sévérité **high/med/low** | repo only |
| **D — Architecture & frontières modules** | code-architect | Layering, couplage, sprawl de feature-flags (LEVIER-1/2, T-001, versions prompt, shadow), simplifications structurelles « fluides », dette de config | repo only |
| **E — Infra / SRE / coût / observabilité** | general-purpose | 15 conteneurs sur hôte 8 GB, resource limits, policy Redis, **Sentry dark**, historique OOM & headroom, **écart déploiement prod #125 vs `main`**, CI, posture sécu hôte (secrets `.env` en clair — T-036), firewall iptables, disque, systemd. **+ sonde live `yourforesight.com`** : latences API réelles, build front servi vs `main`, erreurs console/réseau, fluidité perçue du feed (skill `browse`/`gstack`, public) | SSH read-only + HTTP public |
| **Synthèse** | thread principal (moi) | Fusion, dédup, priorisation P0/P1/P2 (effort × impact × risque), réconciliation PLAN_30D / LEVIER / money-switch, liste « à NE PAS faire » | — |

Frontend hors agent dédié (focus = pipeline+backend) ; couvert au fil de l'eau par
B (contrat API) et E (sonde live).

## 4. Contrat de sûreté (HARD — prod proche-argent)

Chaque brief d'agent inclut **verbatim** ce contrat :

- **Repo** : lecture / grep uniquement. Aucun Edit/Write.
- **Prod** : `ssh foresight` autorisé **uniquement** pour :
  - SQL **`SELECT` only** (jamais `UPDATE/DELETE/INSERT/ALTER/DROP/TRUNCATE`)
  - `docker compose ps|logs|stats|config`, `git log|status|rev-parse`, `df|free|ss|systemctl status`, lecture fichiers
  - **Denylist absolue** : aucun `restart`/`up`/`recreate`/`stop`, aucun `alembic`, aucune écriture Redis (`SET/DEL/FLUSH`), aucun `git pull/push/checkout`, aucune écriture `.env`, aucune commande de mutation.
- **Secrets** : valeurs `.env` jamais imprimées — présence/longueur uniquement (`grep -c`, masquage), comme le pattern déjà utilisé en session.
- **yourforesight.com** : requêtes **GET/HEAD publiques** uniquement, aucune action authentifiée, aucun POST.
- **Findings sourcés** : chaque finding = `file:line` et/ou preuve prod (commande + sortie). Wilson CI95 sur tout chiffre (règle #8 du PLAN_30D).
- **Conscience du travail en vol** : aucune reco ne doit contredire le PLAN_30D signal-quality, le money-switch gaté, ni la discipline prod-vs-`main`. Tension → la signaler dans la liste « à NE PAS faire », ne pas la recommander.

## 5. Livrable

Fichier unique : `docs/audit/2026-05-19-pipeline-backend-simplification-audit.md`
(convention du dossier `docs/audit/` existant).

Structure :
1. **Résumé exécutif** — top 5 leviers de fluidité, chiffrés
2. **Findings par domaine** (A→E) — sourcés, sévérité
3. **Roadmap priorisée** — table : `finding · pourquoi ça nuit à la fluidité · esquisse de fix · effort · impact · risque · conflit PLAN_30D ?` · classés P0/P1/P2
4. **Liste « à NE PAS faire »** — pièges tentants mais en conflit avec le travail en vol / le gating argent

Mise à jour mémoire projet après synthèse (état + pointeur audit).

## 6. Process

Spec approuvé → self-review → revue utilisateur → skill `writing-plans`
(plan d'exécution de la flotte : briefs détaillés par agent, ordre de dispatch
parallèle, garde-fous, format de consolidation) → exécution → livrable + MAJ mémoire.

## 7. Hors scope (explicite)

- Aucun correctif / PR / refactor effectif (audit pur).
- Pas de panel web Hetzner (cloud console) — hôte via SSH only.
- Pas le winrate/RTP du signal en soi (périmètre PLAN_30D) — sauf là où la
  *complexité* de la machinerie de signal nuit à la fluidité.
- Pas d'audit sécu applicatif exhaustif type CSO (l'agent E ne fait que relever
  la posture sécu hôte évidente, ex. secrets `.env` en clair).
- Pas d'installation/config du CLI warden.
