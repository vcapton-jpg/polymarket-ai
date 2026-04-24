"""Pure retrieval / clustering metrics — no I/O, pytest-only dependencies.

All functions accept plain Python types (lists, sets, dicts) and return
deterministic outputs. Bootstrap uses `random.Random(seed)` so results are
reproducible across runs.
"""

from __future__ import annotations

import math
import random
from typing import Iterable


def retrieval_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """|relevant ∩ unique(ranked[:k])| / min(k, |relevant|).

    Returns 0.0 if either input is empty or k <= 0.
    """
    if not relevant_ids or not ranked_ids or k <= 0:
        return 0.0
    top_k = set(ranked_ids[:k])
    hits = len(relevant_ids & top_k)
    denom = min(k, len(relevant_ids))
    return hits / denom


def ndcg_at_k(relevant_ids: set, ranked_ids: list, k: int) -> float:
    """Binary-relevance nDCG@k.

    DCG = Σ rel_i / log2(i + 2) for i in 0..k-1
    IDCG = DCG of the perfect ranking (all relevant first).
    Returns DCG / IDCG, or 0.0 if either is empty.
    """
    if not relevant_ids or not ranked_ids or k <= 0:
        return 0.0
    dcg = 0.0
    for i, rid in enumerate(ranked_ids[:k]):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)
    ideal_hits = min(k, len(relevant_ids))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


def cluster_purity(
    clusters: dict[int, list[int]],
    ground_truth: dict[int, int],
) -> float:
    """Fraction of items (with known ground truth) placed in a cluster whose
    majority label matches their own."""
    total_labeled = 0
    correctly_placed = 0
    for _cluster_id, items in clusters.items():
        labeled_items = [i for i in items if i in ground_truth]
        if not labeled_items:
            continue
        # Majority label in this cluster.
        counts: dict[int, int] = {}
        for i in labeled_items:
            counts[ground_truth[i]] = counts.get(ground_truth[i], 0) + 1
        majority_label = max(counts, key=counts.get)
        correctly_placed += counts[majority_label]
        total_labeled += len(labeled_items)
    return correctly_placed / total_labeled if total_labeled > 0 else 0.0


def bootstrap_ci(
    values: list[float],
    *,
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    """Percentile bootstrap CI on the mean of `values`.

    Returns (mean, ci_low, ci_high). Deterministic given `seed`.
    On empty input, returns (0.0, 0.0, 0.0)."""
    if not values:
        return (0.0, 0.0, 0.0)
    rng = random.Random(seed)
    n = len(values)
    resample_means: list[float] = []
    for _ in range(n_resamples):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        resample_means.append(sum(sample) / n)
    resample_means.sort()
    lo_idx = int(n_resamples * (alpha / 2))
    hi_idx = int(n_resamples * (1 - alpha / 2)) - 1
    hi_idx = max(lo_idx, min(hi_idx, n_resamples - 1))
    mean = sum(values) / n
    return (mean, resample_means[lo_idx], resample_means[hi_idx])


def aggregate(
    per_pair_scores: list[dict],
    *,
    strata: tuple[str, ...] = ("source",),
) -> dict:
    """Aggregate a list of per-pair metric dicts into mean + CI per metric.

    Input shape: [{"retrieval@5": 0.8, "ndcg@10": 0.7, "source": "db_heuristic"}, ...]
    Metric keys = any key not in `strata` or reserved names.

    Returns:
      {
        "retrieval@5": {"mean": ..., "ci_low": ..., "ci_high": ..., "n": ...},
        "ndcg@10": {...},
        "per_source": {"db_heuristic": {"retrieval@5": {...}, ...}, ...}
      }
    """
    if not per_pair_scores:
        return {"per_source": {}}

    reserved = set(strata)
    metric_keys = [k for k in per_pair_scores[0] if k not in reserved]

    def _summarize(rows: list[dict]) -> dict:
        out: dict = {}
        for mk in metric_keys:
            values = [r[mk] for r in rows if mk in r]
            mean, lo, hi = bootstrap_ci(values)
            out[mk] = {"mean": mean, "ci_low": lo, "ci_high": hi, "n": len(values)}
        return out

    result = _summarize(per_pair_scores)
    result["per_source"] = {}
    if "source" in strata:
        by_source: dict[str, list[dict]] = {}
        for r in per_pair_scores:
            by_source.setdefault(r.get("source", "unknown"), []).append(r)
        for src, rows in by_source.items():
            result["per_source"][src] = _summarize(rows)
    return result
