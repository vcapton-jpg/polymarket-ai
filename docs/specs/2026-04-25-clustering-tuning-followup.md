# Clustering Tuning Follow-up (Chantier #2.5)

**Status:** Spec — not yet planned.
**Origin:** Empirical findings during chantier #2 execution (`docs/plans/2026-04-25-clustering-hardening.md`, "Empirical findings appendix").

## Problem

99% of `Event` rows are single-source. Chantier #2 confirmed:

1. Simhash dedup is **not** the cause (min cross-outlet Hamming = 15 bits, 9-bit gate is dormant).
2. `Event.unique_sources_count` is now self-healing (recompute helper wired into both creation paths; backfill `changed=0`).
3. The real cause is **upstream cosine clustering**: median best-match cosine between top-2 sources (Reuters × FirstSquawk) is **0.37** vs the **0.75** cluster threshold. Only 6.3% of Reuters articles have any FirstSquawk article above 0.75 across all-time data; the 120-min time window further filters that.

A `min_unique_sources_per_event` gate cannot be added until cross-outlet clustering actually fires — otherwise it would erase 97.9% of inventory.

## Goal

Re-tune `clustering_cosine_threshold` and `clustering_time_window_minutes` so that cross-outlet corroboration becomes the rule rather than the exception, **without** floor-flooding the event table with false-positive merges. Then enforce the diversity gate.

## Approach (sketch — to be refined during brainstorming)

### Phase A: empirical sweep

Build a **held-out cluster-quality dataset** before tuning anything:

- 200 hand-labelled article pairs, evenly split between (a) same-event-different-outlet, (b) different-event-same-bucket, (c) different-event-different-bucket.
- Source from the last 14 days of `News` × `NewsClean` so the embedding model is stable.
- Pairs labelled by the user (binary: "same event yes/no") in a CSV with `clean_id_a, clean_id_b, label, rationale`.

Then sweep `(cosine_threshold, time_window_minutes)` on a 5×5 grid:

- cosine ∈ {0.45, 0.55, 0.65, 0.70, 0.75}
- window ∈ {120, 240, 360, 720, 1440}

For each cell, measure on the held-out set:

- **Recall** of (a) same-event pairs.
- **Precision** = TP / (TP + FP) where FP is (b) and (c) pairs above threshold within window.
- **Cross-outlet recall** specifically (subset of (a) where outlets differ — the metric we actually care about).

Report the Pareto frontier; pick the cell that maximises cross-outlet recall subject to precision ≥ X (X TBD during brainstorming, plausibly 0.85).

### Phase B: ship the new defaults

Land the chosen `(cosine_threshold, window)` as new defaults in `app/core/config.py`. Re-run the chantier #2 diagnostic and verify the multi-source share rises (target: ≥ 15% of events have ≥ 2 sources, vs current 0.9%).

### Phase C: diversity gate

Now safely add `min_unique_sources_per_event = 2`, with the staging-status idea from chantier #2 plan tasks 8-10 (single-source events go to `processing_status = "pending_multi_source"` and become eligible if a second source corroborates within window). Pin with the test from that plan, which is now ship-safe.

## Open questions for brainstorming

1. **Embedding model first?** A higher-quality embedding model (text-embedding-3-large, or a cross-encoder rerank step) might lift cross-outlet cosine without dropping the threshold. Worth measuring before the cosine sweep.
2. **Time window semantics.** "Last seen within window of anchor" vs "any pairwise overlap within window" — current code is the former; the latter would catch slow-burn stories.
3. **Per-bucket thresholds?** Politics articles cluster differently from finance (different vocabulary density). May need separate thresholds.
4. **Rejection memory.** When a single-source article is rejected by the gate, does it stay queued forever waiting for corroboration, or does it expire? What's the staging GC?

## Out of scope

- Re-architecting the clusterer itself (HDBSCAN over a rolling window, etc.) — keep this incremental.
- LLM-based "is this the same event?" pairwise classifier — interesting but separate chantier.
- Source-weight in the dedup decision (currently absent) — separate chantier.

## Definition of done

- `(cosine_threshold, window)` chosen via measured sweep, not eyeballed.
- `min_unique_sources_per_event = 2` enforced at `_run_full_scoring_pipeline` entry.
- `clustering-diversity-hourly` beat shows ≥ 15% of events with ≥ 2 sources after 7 days of new ingestion.
- BLUEPRINT updated with the new thresholds and the held-out evaluation methodology.

## Pre-requisites

- Chantier #2 shipped (recompute helper, backfill, diagnostic, hourly beat). ✅
- Held-out cluster-quality dataset built. ❌ (Phase A deliverable.)
