"""Orchestration of one eval run: load pairs → score against candidates → aggregate."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.eval.labels import load_pairs
from app.eval.metrics import aggregate, ndcg_at_k, retrieval_at_k

logger = logging.getLogger(__name__)

_SURFACE_TO_PAIR_SURFACE = {
    "news": "article_to_event",
    "event": "event_to_market",
    "market": "market_to_article",
}
# "all" handled by dispatching to each surface in turn (caller level).


@dataclass
class EvalReport:
    variant: str
    surface: str
    metrics: dict[str, dict]
    per_source: dict[str, dict]
    generated_at: datetime
    git_sha: str
    n_pairs: int
    n_skipped: int


async def run_eval(
    session: AsyncSession,
    *,
    variant: Literal["v1", "v2"],
    surface: str,
) -> EvalReport:
    if surface not in _SURFACE_TO_PAIR_SURFACE:
        raise ValueError(
            f"surface must be one of {list(_SURFACE_TO_PAIR_SURFACE)}; got {surface!r}"
        )
    pair_surface = _SURFACE_TO_PAIR_SURFACE[surface]
    pairs = await load_pairs(session, surface=pair_surface, limit=500)

    # Scope down to pairs whose query actually has an embedding in this variant.
    # Queries without an embedding are not "in scope" for this eval run — they
    # represent data that hasn't been embedded yet, not an eval failure. Only
    # count `n_skipped` for in-scope queries that fail for some other reason
    # (e.g. empty candidate pool).
    in_scope: list[tuple[Any, list[float]]] = []
    for p in pairs:
        query_emb = await _fetch_embedding_for_query(session, pair_surface, p.query_id, variant)
        if query_emb is None:
            continue
        in_scope.append((p, query_emb))

    per_pair: list[dict[str, Any]] = []
    n_skipped = 0

    for p, query_emb in in_scope:
        candidate_rows = await _fetch_candidate_pool(session, pair_surface, p.query_id, variant)
        scored: list[tuple[int | str, float]] = []
        for cand_id, cand_emb in candidate_rows:
            if cand_emb is None:
                continue
            scored.append((cand_id, _dot(query_emb, cand_emb)))
        if not scored:
            n_skipped += 1
            continue
        scored.sort(key=lambda t: -t[1])
        ranked_ids = [cid for cid, _ in scored]
        per_pair.append({
            "retrieval@5": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=5),
            "retrieval@10": retrieval_at_k(set(p.relevant_ids), ranked_ids, k=10),
            "ndcg@10": ndcg_at_k(set(p.relevant_ids), ranked_ids, k=10),
            "source": p.source,
        })

    agg = aggregate(per_pair, strata=("source",))
    per_source = agg.pop("per_source", {})

    return EvalReport(
        variant=variant,
        surface=surface,
        metrics=agg,
        per_source=per_source,
        generated_at=datetime.now(timezone.utc),
        git_sha=_git_sha(),
        n_pairs=len(per_pair),
        n_skipped=n_skipped,
    )


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "unknown"


async def _fetch_embedding_for_query(
    session: AsyncSession, pair_surface: str, query_id, variant: str
) -> list[float] | None:
    from app.db.models import Event, Market, NewsClean
    col = "embedding" if variant == "v1" else "embedding_v2"
    if pair_surface == "event_to_market":
        stmt = select(getattr(Event, col)).where(Event.id == query_id)
    elif pair_surface == "article_to_event":
        stmt = select(getattr(NewsClean, col)).where(NewsClean.id == query_id)
    else:  # market_to_article
        stmt = select(getattr(Market, col)).where(Market.market_id == query_id)
    row = (await session.execute(stmt)).scalar_one_or_none()
    return list(row) if row is not None else None


async def _fetch_candidate_pool(
    session: AsyncSession, pair_surface: str, query_id, variant: str
) -> list[tuple]:
    """Return (candidate_id, embedding) pairs shaped like the prod consumer would
    see. For simplicity in the first cut, the pool is 'all candidates of the
    relevant type with the same bucket'. More nuanced pools (±time windows) can
    be added per surface if needed."""
    from app.db.models import Event, Market, NewsClean
    col = "embedding" if variant == "v1" else "embedding_v2"
    if pair_surface == "event_to_market":
        # Candidate pool: active, non-closed markets in the same bucket.
        bucket = (await session.execute(
            select(Event.bucket).where(Event.id == query_id)
        )).scalar_one_or_none()
        stmt = select(Market.market_id, getattr(Market, col)).where(
            Market.active.is_(True),
            Market.closed.is_(False),
            Market.bucket == bucket,
        )
    elif pair_surface == "article_to_event":
        # Candidate pool: events in the same bucket (±time window ignored here for simplicity).
        bucket = (await session.execute(
            select(NewsClean.bucket).where(NewsClean.id == query_id)
        )).scalar_one_or_none()
        stmt = select(Event.id, getattr(Event, col)).where(Event.bucket == bucket)
    else:  # market_to_article
        bucket = (await session.execute(
            select(Market.bucket).where(Market.market_id == query_id)
        )).scalar_one_or_none()
        stmt = select(NewsClean.id, getattr(NewsClean, col)).where(NewsClean.bucket == bucket)
    rows = (await session.execute(stmt)).all()
    return [(r[0], list(r[1]) if r[1] is not None else None) for r in rows]


def report_to_json(report: EvalReport) -> str:
    d = asdict(report)
    d["generated_at"] = report.generated_at.isoformat()
    return json.dumps(d, indent=2, default=str)


def diff_reports(baseline: EvalReport, candidate: EvalReport) -> dict:
    """Per-metric delta + verdict vs baseline.

    Verdict:
      - "improved"  if candidate's CI_low > baseline's CI_high (disjoint, candidate higher)
      - "regressed" if candidate's CI_high < baseline's CI_low (disjoint, candidate lower)
      - "flat"      otherwise (overlap or no data)
    """
    out: dict[str, dict] = {}
    for metric, stats in candidate.metrics.items():
        base = baseline.metrics.get(metric, {})
        cand_mean = stats.get("mean", 0.0)
        base_mean = base.get("mean", 0.0)
        cand_ci_low = stats.get("ci_low", 0.0)
        cand_ci_high = stats.get("ci_high", 0.0)
        base_ci_low = base.get("ci_low", 0.0)
        base_ci_high = base.get("ci_high", 0.0)
        if cand_ci_low > base_ci_high:
            verdict = "improved"
        elif cand_ci_high < base_ci_low:
            verdict = "regressed"
        else:
            verdict = "flat"
        out[metric] = {
            "baseline_mean": base_mean,
            "candidate_mean": cand_mean,
            "delta": cand_mean - base_mean,
            "verdict": verdict,
        }
    return out
