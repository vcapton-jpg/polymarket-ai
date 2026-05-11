"""Offline tuner: coordinate descent over 5 free heuristic weights against a
short-horizon Brier objective with a 3-check promotion gate.

Parameter space (sum-to-1 constraints handled by deriving 4 weights):

    Free:    w_llm, w_liquidity, w_spread, w_freshness, strength_weight
    Derived: w_source        = 0.10   (fixed — small effect, reduce search)
             w_confirmation  = 1 - w_freshness - w_source - w_llm
             w_time_to_res   = 1 - w_liquidity - w_spread
             trade_weight    = 1 - strength_weight
"""
from __future__ import annotations

import argparse
import asyncio
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import text

from app.db.database import async_session_factory
from app.measurement.heuristic_variant import predict_heuristic
from app.measurement.metrics import brier_from_outcome, simulated_pnl_eur
from app.scoring.weights import HeuristicWeights


@dataclass(frozen=True)
class Sample:
    features: dict
    llm_combined: float
    direction: str
    price_t1h: float


@dataclass(frozen=True)
class CandidateResult:
    weights: HeuristicWeights
    brier_mean: float
    pnl_mean: float
    n: int
    n_brier_defined: int


def _binarise(price: float) -> int | None:
    if price >= 0.95:
        return 1
    if price <= 0.05:
        return 0
    return None


def evaluate_candidate(w: HeuristicWeights, samples: Iterable) -> CandidateResult:
    """Score the sample set under `w`; return Brier mean + P&L mean.

    Accepts any iterable of objects with `features`, `llm_combined`, `direction`,
    `price_t1h` attributes (duck-typed to avoid coupling with the tuner's own
    `Sample` dataclass — tests pass their own dataclass).
    """
    briers: list[float] = []
    pnls: list[float] = []
    n = 0
    for s in samples:
        n += 1
        pred = predict_heuristic(
            weights=w, features=s.features, llm_combined=s.llm_combined,
            direction=s.direction,
        )
        if pred.probability is None:
            continue
        bin_out = _binarise(s.price_t1h)
        if bin_out is not None:
            b = brier_from_outcome(pred.probability, bin_out)
            if b is not None:
                briers.append(b)
        if s.direction in ("BUY_YES", "BUY_NO"):
            pnls.append(simulated_pnl_eur(
                direction=s.direction, probability=pred.probability,
                price_resolved=s.price_t1h,
            ))
    return CandidateResult(
        weights=w,
        brier_mean=sum(briers) / len(briers) if briers else float("inf"),
        pnl_mean=sum(pnls) / len(pnls) if pnls else 0.0,
        n=n,
        n_brier_defined=len(briers),
    )


def _safe_weights(
    *,
    w_freshness: float,
    w_source: float,
    w_llm: float,
    w_liquidity: float,
    w_spread: float,
    strength_weight: float,
) -> HeuristicWeights | None:
    w_confirmation = 1.0 - w_freshness - w_source - w_llm
    w_ttr = 1.0 - w_liquidity - w_spread
    trade_weight = 1.0 - strength_weight
    if w_confirmation < 0.0 or w_ttr < 0.0 or trade_weight < 0.0:
        return None
    try:
        return HeuristicWeights(
            w_freshness=w_freshness, w_source=w_source,
            w_confirmation=w_confirmation, w_llm=w_llm,
            w_liquidity=w_liquidity, w_spread=w_spread,
            w_time_to_resolution=w_ttr,
            strength_weight=strength_weight, trade_weight=trade_weight,
        )
    except ValueError:
        return None


_GRID = {
    "w_freshness":     [0.05, 0.15, 0.25, 0.35, 0.50],
    "w_llm":           [0.30, 0.45, 0.60, 0.75, 0.90],
    "w_liquidity":     [0.20, 0.40, 0.60],
    "w_spread":        [0.15, 0.35, 0.50],
    "strength_weight": [0.50, 0.65, 0.75, 0.85],
}


def coordinate_descent(
    samples: list,
    *,
    passes: int = 2,
    w_source_fixed: float = 0.10,
) -> CandidateResult:
    """Two passes of coordinate descent over the 5 free parameters.

    Each pass iterates in a fixed order, picks the grid value minimising
    brier_mean conditional on the current other parameters. Deterministic.
    """
    current = HeuristicWeights.frozen_v1()
    best = evaluate_candidate(current, samples)
    order = ("w_freshness", "w_llm", "w_liquidity", "w_spread", "strength_weight")

    for _ in range(passes):
        for param in order:
            for candidate_val in _GRID[param]:
                kwargs = {
                    "w_freshness": current.w_freshness,
                    "w_source": w_source_fixed,
                    "w_llm": current.w_llm,
                    "w_liquidity": current.w_liquidity,
                    "w_spread": current.w_spread,
                    "strength_weight": current.strength_weight,
                }
                kwargs[param] = candidate_val
                trial = _safe_weights(**kwargs)
                if trial is None:
                    continue
                result = evaluate_candidate(trial, samples)
                if (
                    result.brier_mean < best.brier_mean
                    or (
                        result.brier_mean == best.brier_mean
                        and result.pnl_mean > best.pnl_mean
                    )
                ):
                    best = result
                    current = trial
    return best


def evaluation_gate(
    *,
    candidate: CandidateResult,
    baseline_v1: CandidateResult,
    per_bucket: dict[str, tuple[CandidateResult, CandidateResult]] | None = None,
    pnl_slip_tolerance: float = 0.05,
    bucket_brier_regression_cap: float = 0.05,
) -> dict:
    """Apply the 3-check gate: Brier CI-disjoint, P&L not down >5%, no bucket regression >5%."""
    def _se(brier: float, n: int) -> float:
        if n < 2:
            return float("inf")
        return (brier * (1 - brier) / n) ** 0.5

    cand_se = _se(candidate.brier_mean, candidate.n_brier_defined)
    base_se = _se(baseline_v1.brier_mean, baseline_v1.n_brier_defined)
    cand_hi = candidate.brier_mean + 1.96 * cand_se
    base_lo = baseline_v1.brier_mean - 1.96 * base_se
    brier_disjoint = cand_hi < base_lo

    pnl_floor = baseline_v1.pnl_mean * (1.0 - pnl_slip_tolerance)
    pnl_ok = candidate.pnl_mean >= pnl_floor

    bucket_ok = True
    bucket_diagnostics: dict[str, dict] = {}
    if per_bucket:
        for bucket_name, (cand_b, base_b) in per_bucket.items():
            regression = cand_b.brier_mean - base_b.brier_mean
            passed = regression <= bucket_brier_regression_cap
            bucket_diagnostics[bucket_name] = {
                "candidate_brier": cand_b.brier_mean,
                "baseline_brier": base_b.brier_mean,
                "regression": regression,
                "passed": passed,
            }
            if not passed:
                bucket_ok = False

    return {
        "passed": brier_disjoint and pnl_ok and bucket_ok,
        "brier_disjoint": brier_disjoint,
        "pnl_ok": pnl_ok,
        "bucket_ok": bucket_ok,
        "candidate_brier": candidate.brier_mean,
        "candidate_pnl": candidate.pnl_mean,
        "baseline_brier": baseline_v1.brier_mean,
        "baseline_pnl": baseline_v1.pnl_mean,
        "pnl_floor": pnl_floor,
        "buckets": bucket_diagnostics,
    }


async def _fetch_samples(horizon: str) -> list[Sample]:
    col = f"price_{horizon}"
    sql = text(
        f"""SELECT s.id, s.direction,
                   sp.predicted_probability,
                   emf.freshness_factor, emf.source_weight, emf.confirmation_factor,
                   emf.liquidity_factor, emf.spread_penalty, emf.time_to_resolution_factor,
                   emf.impact_strength, emf.llm_confidence,
                   so.{col} AS price_horizon
            FROM signals s
            JOIN signal_predictions sp ON sp.signal_id = s.id AND sp.variant = 'heuristic_v1'
            JOIN signal_outcomes so ON so.signal_id = s.id
            LEFT JOIN event_market_features emf
              ON emf.event_id = s.event_id AND emf.market_id = s.market_id
            WHERE so.{col} IS NOT NULL"""
    )
    samples: list[Sample] = []
    async with async_session_factory() as s:
        rows = (await s.execute(sql)).all()
    for r in rows:
        (_sid, direction, _prob,
         fresh, src, confirm, liq, spread, ttr,
         impact, llm_conf, price) = r
        llm_combined: float | None = None
        if impact is not None and llm_conf is not None:
            llm_combined = float(impact) * 0.65 + float(llm_conf) * 0.35
        samples.append(Sample(
            features={
                "freshness": float(fresh) if fresh is not None else 0.5,
                "source_weight": float(src) if src is not None else 0.5,
                "confirmation": float(confirm) if confirm is not None else 0.5,
                "liquidity": float(liq) if liq is not None else 0.5,
                "spread": float(spread) if spread is not None else 0.5,
                "time_to_resolution": float(ttr) if ttr is not None else 0.5,
            },
            llm_combined=llm_combined if llm_combined is not None else 0.5,
            direction=direction,
            price_t1h=float(price),
        ))
    return samples


async def _main_async(*, horizon: str, out_path: str, passes: int) -> None:
    samples = await _fetch_samples(horizon)
    if not samples:
        print(f"No joined samples at horizon={horizon}; exit.")
        return
    baseline = evaluate_candidate(HeuristicWeights.frozen_v1(), samples)
    best = coordinate_descent(samples, passes=passes)
    gate = evaluation_gate(candidate=best, baseline_v1=baseline)
    payload = {
        "generated_at": str(date.today()),
        "horizon": horizon,
        "n_samples": len(samples),
        "baseline_v1": {
            "brier_mean": baseline.brier_mean, "pnl_mean": baseline.pnl_mean,
            "n_brier_defined": baseline.n_brier_defined,
        },
        "candidate": {
            "weights": best.weights.__dict__,
            "brier_mean": best.brier_mean,
            "pnl_mean": best.pnl_mean,
            "n_brier_defined": best.n_brier_defined,
        },
        "gate": gate,
        "gate_status": "passed" if gate["passed"] else "failed",
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(f"wrote {out_path} — gate_status={payload['gate_status']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune heuristic weights via coordinate descent.")
    parser.add_argument("--horizon", choices=("t15min", "t1h", "t24h"), default="t1h")
    parser.add_argument("--passes", type=int, default=2)
    parser.add_argument(
        "--out",
        default=f"docs/audit/heuristic_weights_candidate_{date.today().isoformat()}.json",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(horizon=args.horizon, out_path=args.out, passes=args.passes))


if __name__ == "__main__":
    main()
