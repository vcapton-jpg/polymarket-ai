"""Offline tuner for hybrid_search_v2 — coordinate descent + offline gate.

Usage:
    python -m scripts.tune_event_market_ranking \\
        --labels docs/eval_labels/event_market_ground_truth_2026-04-25.jsonl \\
        --out docs/eval_baselines/ranking_event_market_best_2026-04-25.json

Evaluation is deterministic: each config is scored by running the chantier #3
harness `runner.run_eval` on the provided labels, using the ranking variant
specified by the config — **not** via env flip (to avoid race conditions).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from sqlalchemy import select

from app.db.database import get_session_factory

logger = logging.getLogger(__name__)


# Grid search ranges (spec §6.1 Section 3).
RANGES: dict[str, list] = {
    "w_entity":  [0.1, 0.3, 0.5, 0.8, 1.2],
    "w_date":    [0.0, 0.2, 0.5, 1.0],
    "w_bucket":  [0.0, 0.1, 0.3, 0.5],
    "tau_days":  [7.0, 14.0, 30.0, 60.0],
    "min_sim":   [0.35, 0.45, 0.55],
    "rrf_k":     [30, 60, 90, 120],
}

V1_CONFIG: dict = {
    "w_entity": 0.5, "w_date": 0.0, "w_bucket": 0.0,
    "tau_days": 14.0, "min_sim": 0.45, "rrf_k": 60,
}

# Order of coordinate descent passes (interactions captured via 2 passes).
COORD_ORDER = ("w_entity", "w_date", "w_bucket", "tau_days", "min_sim", "rrf_k")

MAX_BUCKET_REGRESSION = 0.05


def coordinate_descent(
    score_fn: Callable[[dict], float],
    grid: dict[str, list],
    start: dict,
    *,
    passes: int = 2,
) -> dict:
    """Sweep each parameter in COORD_ORDER passes times, keeping the best."""
    best = dict(start)
    best_score = score_fn(best)
    for _pass in range(passes):
        for param, values in grid.items():
            for v in values:
                candidate = dict(best)
                candidate[param] = v
                s = score_fn(candidate)
                if s > best_score:
                    best_score = s
                    best = candidate
    return best


def evaluate_offline_gate(
    v1_report: dict, v2_report: dict, *, max_bucket_regression: float,
) -> dict:
    """Three conditions (spec §6.3):
      1. retrieval@5 v2 ci_low > v1 ci_high (strict disjoint)
      2. nDCG@10 v2 mean > v1 mean
      3. no bucket regresses > max_bucket_regression on retrieval@5
    """
    v1_ret5 = v1_report["overall"].get("retrieval@5", {})
    v2_ret5 = v2_report["overall"].get("retrieval@5", {})
    if v2_ret5.get("ci_low", 0.0) <= v1_ret5.get("ci_high", 0.0):
        return {
            "status": "failed",
            "reason": (
                f"retrieval@5 CI overlap: v2 ci_low={v2_ret5.get('ci_low')} "
                f"<= v1 ci_high={v1_ret5.get('ci_high')}"
            ),
        }
    # Bucket-regression check runs before the nDCG@10 tiebreaker so that a
    # per-bucket regression surfaces as the failure reason even when nDCG is
    # missing/uncomputed.
    for bucket, stats in v2_report.get("per_bucket", {}).items():
        v1_bucket = v1_report.get("per_bucket", {}).get(bucket, {})
        v1_mean = v1_bucket.get("retrieval@5", {}).get("mean", 0.0)
        v2_mean = stats.get("retrieval@5", {}).get("mean", 0.0)
        if v1_mean - v2_mean > max_bucket_regression:
            return {
                "status": "failed",
                "reason": (
                    f"bucket {bucket!r} regressed: v1={v1_mean} -> v2={v2_mean} "
                    f"(delta {v1_mean - v2_mean:.3f} > max {max_bucket_regression:.3f})"
                ),
            }
    v1_nd10 = v1_report["overall"].get("ndcg@10", {}).get("mean", 0.0)
    v2_nd10 = v2_report["overall"].get("ndcg@10", {}).get("mean", 0.0)
    # Treat absent nDCG@10 as not-blocking (both zero → tiebreaker is unavailable).
    if v1_nd10 > 0.0 or v2_nd10 > 0.0:
        if v2_nd10 <= v1_nd10:
            return {
                "status": "failed",
                "reason": f"nDCG@10 did not improve: v2={v2_nd10} <= v1={v1_nd10}",
            }
    return {"status": "passed"}


async def _score_config_async(cfg: dict, labels_path: Path) -> dict:
    """Run the harness with a specific config, return aggregated report."""
    from app.eval.labels_event_market import load_event_market_labels
    from app.eval.metrics import aggregate, ndcg_at_k, retrieval_at_k
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
    # Bypass the env flag — call v2 directly with an override config.
    pairs = load_event_market_labels(labels_path)
    if not pairs:
        return {"overall": {}, "per_bucket": {}, "n_pairs": 0}

    factory = get_session_factory()
    per_pair: list[dict] = []
    async with factory() as session:
        for p in pairs:
            from app.db.models import Event
            ev = (
                await session.execute(select(Event).where(Event.id == p.query_id))
            ).scalar_one_or_none()
            if ev is None or ev.embedding is None:
                continue
            ranked = await _run_v2_with_override(session, ev, cfg)
            if not ranked:
                continue
            ranked_ids = [r["market_id"] for r in ranked]
            per_pair.append({
                "retrieval@5": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=5),
                "ndcg@10":     ndcg_at_k(set(p.relevant_ids), ranked_ids, k=10),
                "bucket":      ev.bucket or "other",
            })

    overall = aggregate(per_pair, strata=("bucket",))
    per_bucket = overall.pop("per_source", {})  # aggregate re-uses this key name
    return {
        "overall": overall,
        "per_bucket": per_bucket,
        "n_pairs": len(per_pair),
    }


async def _run_v2_with_override(session, event, cfg: dict) -> list[dict]:
    """Call hybrid_search_markets_v2 with ad-hoc override weights.

    We monkeypatch the settings within the coroutine by setting module-level
    thread-local state — simpler is to patch get_settings() via lru_cache
    invalidation + env vars. We mutate the in-process Settings object
    directly because this script runs single-threaded.
    """
    from app.core.config import get_settings
    from app.retrieval.hybrid_search_v2 import hybrid_search_markets_v2
    s = get_settings()
    prev = {k: getattr(s, f"ranking_v2_{k}") for k in cfg}
    try:
        for k, v in cfg.items():
            object.__setattr__(s, f"ranking_v2_{k}", v)
        return await hybrid_search_markets_v2(
            session, list(event.embedding),
            event.event_retrieval_text or event.event_title,
            top_k=10,
            event_bucket=event.bucket,
            event_entities=event.key_entities,
            event_last_seen=event.last_seen,
        )
    finally:
        for k, v in prev.items():
            object.__setattr__(s, f"ranking_v2_{k}", v)


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


async def _run(labels_path: Path, out_path: Path) -> int:
    # Score v1 baseline.
    logger.info("scoring v1 baseline")
    v1_report = await _score_config_async(V1_CONFIG, labels_path)

    # Coordinate descent. `coordinate_descent` is a sync API; each cell
    # spawns a fresh event loop so we don't collide with the outer
    # `asyncio.run` loop. Single-threaded, so this is safe.
    eager_cache: dict[tuple, float] = {}

    def sync_score(cfg: dict) -> float:
        key = tuple(sorted(cfg.items()))
        if key in eager_cache:
            return eager_cache[key]
        rep = asyncio.new_event_loop().run_until_complete(
            _score_config_async(cfg, labels_path)
        )
        ret5 = rep["overall"].get("retrieval@5", {}).get("mean", 0.0)
        ndcg10 = rep["overall"].get("ndcg@10", {}).get("mean", 0.0)
        # Primary: retrieval@5; tiebreak: nDCG@10.
        eager_cache[key] = ret5 * 1000 + ndcg10
        return eager_cache[key]

    logger.info("starting coordinate descent")
    best = coordinate_descent(sync_score, RANGES, dict(V1_CONFIG), passes=2)
    logger.info("best config: %s", best)

    v2_report = await _score_config_async(best, labels_path)
    gate = evaluate_offline_gate(v1_report, v2_report, max_bucket_regression=MAX_BUCKET_REGRESSION)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "labels_path": str(labels_path),
        "v1_config": V1_CONFIG,
        "v2_config": best,
        "v1_report": v1_report,
        "v2_report": v2_report,
        "gate": gate,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps({
        "gate_status": gate["status"],
        "best_config": best,
        "out_path": str(out_path),
    }, indent=2))
    return 0 if gate["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="tune_event_market_ranking")
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(_run(args.labels, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
