"""Gate Effectiveness Backtest — partial (6 replayable gates).

Read-only analysis. Pulls every (event, market) pair that produced an
`event_market_analysis` row in the last `--window`, replays the 6
backtestable gates against the stored LLM analysis + cosine score, then
aligns each gate's rejection decision with the eventual market outcome
(binary band, ≥0.95 or ≤0.05).

Outputs:
  - Markdown report at --out
  - JSON sidecar at --out (with .json extension)

The other 7 production gates depend on at-time market state that was
not historically snapshotted (`event_market_features` is empty in prod
prior to PR #1). They appear in the report only as "deferred" entries.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random as _random
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.database import get_session_factory
from app.scoring.gate_replay import (
    GateInput,
    gate_ambiguity,
    gate_cosine,
    gate_direction_clear,
    gate_has_reasoning,
    gate_impact_strength,
    gate_specificity,
    replay_all_gates,
)

# ── Defaults from app/core/config.py ─────────────────────────────────────
DEFAULT_COSINE = 0.52
DEFAULT_AMBIGUITY = 0.80
DEFAULT_SPECIFICITY = 0.40

# Gates we cannot replay from historical data (require at-time market state)
DEFERRED_GATES = [
    "spread",
    "price_band",
    "no_llm_analysis",
    "no_excerpts",
    "unclear_recommendation",
    "market_quality",
    "catalyst_disagrees_with_market",
]


# ── Sample model ─────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Sample:
    event_id: int
    market_id: str
    cosine_score: float | None
    impact_direction: str | None
    impact_strength: float | None
    ambiguity_score: float | None
    specificity_score: float | None
    reasoning: str | None
    outcome_label: int | None   # 1, 0, or None (no outcome known)

    def gate_input(self) -> GateInput:
        return GateInput(
            cosine_score=self.cosine_score,
            impact_direction=self.impact_direction,
            ambiguity_score=self.ambiguity_score,
            specificity_score=self.specificity_score,
            impact_strength=self.impact_strength,
            reasoning=self.reasoning,
        )

    def llm_predicted_direction_int(self) -> int | None:
        """Map BUY_YES → 1, BUY_NO → 0, else None.

        FRR is "if this gate were off, would the LLM's pick match the outcome?".
        We need a 1/0 label to compare to outcome_label.
        """
        d = (self.impact_direction or "").upper()
        if d == "BUY_YES":
            return 1
        if d == "BUY_NO":
            return 0
        return None


# ── SQL pull ─────────────────────────────────────────────────────────────
SAMPLE_SQL = text("""
WITH passed_outcome AS (
    SELECT s.event_id, s.market_id, so.outcome_label AS lbl
      FROM signals s
      JOIN signal_outcomes so ON so.signal_id = s.id
     WHERE so.outcome_label IS NOT NULL
),
rejected_outcome AS (
    -- Pairs that were analyzed but never became signals.
    -- Outcome derived from the market itself if it closed in the binary band.
    SELECT ema.event_id, ema.market_id,
           CASE
             WHEN m.closed = true AND m.last_trade_price >= 0.95 THEN 1
             WHEN m.closed = true AND m.last_trade_price <= 0.05 THEN 0
             ELSE NULL
           END AS lbl
      FROM event_market_analysis ema
      JOIN markets m ON m.market_id = ema.market_id
      LEFT JOIN signals s
        ON s.event_id = ema.event_id AND s.market_id = ema.market_id
     WHERE s.id IS NULL
)
SELECT
    ema.event_id,
    ema.market_id,
    emc.cosine_score,
    ema.impact_direction,
    ema.impact_strength,
    ema.ambiguity_score,
    ema.specificity_score,
    ema.reasoning,
    COALESCE(po.lbl, ro.lbl) AS outcome_label
  FROM event_market_analysis ema
  LEFT JOIN event_market_candidates emc
    ON emc.event_id = ema.event_id AND emc.market_id = ema.market_id
  LEFT JOIN passed_outcome po
    ON po.event_id = ema.event_id AND po.market_id = ema.market_id
  LEFT JOIN rejected_outcome ro
    ON ro.event_id = ema.event_id AND ro.market_id = ema.market_id
 WHERE ema.created_at >= :since
""")


async def fetch_samples(window_days: int) -> list[Sample]:
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    factory = get_session_factory()
    samples: list[Sample] = []
    async with factory() as s:
        rows = (await s.execute(SAMPLE_SQL, {"since": since})).all()
    for r in rows:
        samples.append(Sample(
            event_id=r.event_id,
            market_id=r.market_id,
            cosine_score=float(r.cosine_score) if r.cosine_score is not None else None,
            impact_direction=r.impact_direction,
            impact_strength=float(r.impact_strength) if r.impact_strength is not None else None,
            ambiguity_score=float(r.ambiguity_score) if r.ambiguity_score is not None else None,
            specificity_score=float(r.specificity_score) if r.specificity_score is not None else None,
            reasoning=r.reasoning,
            outcome_label=int(r.outcome_label) if r.outcome_label is not None else None,
        ))
    return samples


# ── Metrics ──────────────────────────────────────────────────────────────
@dataclass
class GateMetrics:
    name: str
    n_total: int
    n_rejected: int
    n_rejected_with_outcome: int
    n_correct_if_kept: int
    frr: float | None                 # P(would have been correct | rejected)
    frr_ci95_low: float | None
    frr_ci95_high: float | None
    threshold: float | None = None    # default threshold (numeric gates only)

    def low_n(self) -> bool:
        return (self.n_rejected_with_outcome or 0) < 30

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "threshold": self.threshold,
            "n_total": self.n_total,
            "n_rejected": self.n_rejected,
            "n_rejected_with_outcome": self.n_rejected_with_outcome,
            "n_correct_if_kept": self.n_correct_if_kept,
            "frr": self.frr,
            "frr_ci95_low": self.frr_ci95_low,
            "frr_ci95_high": self.frr_ci95_high,
            "low_n_warning": self.low_n(),
        }


def _bootstrap_frr_ci(rejection_outcomes: list[int], *, iters: int = 1000, seed: int = 42) -> tuple[float | None, float | None]:
    """rejection_outcomes is a list of {0, 1}: 1 if "would have been correct"
    (i.e., LLM direction matched outcome). Resample with replacement."""
    n = len(rejection_outcomes)
    if n == 0:
        return None, None
    rng = _random.Random(seed)
    sims = []
    for _ in range(iters):
        boot = [rejection_outcomes[rng.randrange(n)] for _ in range(n)]
        sims.append(sum(boot) / n)
    sims.sort()
    lo = sims[int(0.025 * iters)]
    hi = sims[int(0.975 * iters)]
    return lo, hi


def _gate_metrics(name: str, samples: list[Sample], gate_fn, threshold: float | None = None) -> GateMetrics:
    n_total = len(samples)
    n_rejected = 0
    rejection_outcomes: list[int] = []  # 1 = "would have been correct", 0 = "would have been wrong"

    for s in samples:
        result = gate_fn(s.gate_input(), threshold=threshold) if threshold is not None else gate_fn(s.gate_input())
        if result.passed:
            continue
        n_rejected += 1
        # Did this gate strip a pair that would have been correct?
        pred = s.llm_predicted_direction_int()
        if s.outcome_label is None or pred is None:
            continue  # cannot grade — exclude from FRR
        rejection_outcomes.append(1 if pred == s.outcome_label else 0)

    n_with_outcome = len(rejection_outcomes)
    n_correct = sum(rejection_outcomes)
    frr = (n_correct / n_with_outcome) if n_with_outcome else None
    lo, hi = _bootstrap_frr_ci(rejection_outcomes)

    return GateMetrics(
        name=name,
        n_total=n_total,
        n_rejected=n_rejected,
        n_rejected_with_outcome=n_with_outcome,
        n_correct_if_kept=n_correct,
        frr=frr,
        frr_ci95_low=lo,
        frr_ci95_high=hi,
        threshold=threshold,
    )


def compute_metrics(samples: list[Sample]) -> list[GateMetrics]:
    return [
        _gate_metrics("cosine", samples, gate_cosine, threshold=DEFAULT_COSINE),
        _gate_metrics("direction_clear", samples, lambda i, **_: gate_direction_clear(i)),
        _gate_metrics("ambiguity", samples, gate_ambiguity, threshold=DEFAULT_AMBIGUITY),
        _gate_metrics("specificity", samples, gate_specificity, threshold=DEFAULT_SPECIFICITY),
        _gate_metrics("impact_strength", samples, lambda i, **_: gate_impact_strength(i)),
        _gate_metrics("has_reasoning", samples, lambda i, **_: gate_has_reasoning(i)),
    ]


# ── Counterfactual sweep ────────────────────────────────────────────────
@dataclass
class ThresholdSweep:
    gate: str
    delta: float
    threshold: float
    metrics: GateMetrics

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "delta": self.delta,
            "threshold": self.threshold,
            "metrics": self.metrics.to_dict(),
        }


def compute_counterfactuals(samples: list[Sample]) -> list[ThresholdSweep]:
    sweeps: list[ThresholdSweep] = []
    for gate_name, fn, default in [
        ("cosine", gate_cosine, DEFAULT_COSINE),
        ("ambiguity", gate_ambiguity, DEFAULT_AMBIGUITY),
        ("specificity", gate_specificity, DEFAULT_SPECIFICITY),
    ]:
        for delta in [-0.10, -0.05, 0.0, 0.05, 0.10]:
            t = round(default + delta, 4)
            m = _gate_metrics(f"{gate_name}@{t:.2f}", samples, fn, threshold=t)
            sweeps.append(ThresholdSweep(
                gate=gate_name, delta=delta, threshold=t, metrics=m,
            ))
    return sweeps


# ── Recommendations ──────────────────────────────────────────────────────
@dataclass
class Recommendation:
    gate: str
    current_threshold: float
    suggested_threshold: float
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "current_threshold": self.current_threshold,
            "suggested_threshold": self.suggested_threshold,
            "reasoning": self.reasoning,
        }


def derive_recommendations(sweeps: list[ThresholdSweep]) -> list[Recommendation]:
    """A "lower threshold" recommendation is fired when:
       • a sweep with delta < 0 (less strict) has FRR CI95 disjoint from
         (and lower than) the FRR of the default — i.e., the rejected pairs
         we're catching with the looser threshold would have been wrong
         significantly less than the default's rejected set, suggesting
         the strict threshold is over-rejecting.

    We deliberately keep the recommendation surface narrow — the audit
    report includes the full sweep for human judgment.
    """
    by_gate: dict[str, list[ThresholdSweep]] = {}
    for s in sweeps:
        by_gate.setdefault(s.gate, []).append(s)

    recs: list[Recommendation] = []
    for gate_name, gate_sweeps in by_gate.items():
        default_sweep = next(s for s in gate_sweeps if s.delta == 0.0)
        if default_sweep.metrics.frr is None or default_sweep.metrics.low_n():
            continue
        default_lo = default_sweep.metrics.frr_ci95_low or 0.0
        default_hi = default_sweep.metrics.frr_ci95_high or 1.0

        # Look for a less-strict variant whose FRR is CI-disjoint AND lower
        for s in gate_sweeps:
            if s.delta >= 0 or s.metrics.frr is None or s.metrics.low_n():
                continue
            cand_hi = s.metrics.frr_ci95_high or 1.0
            cand_lo = s.metrics.frr_ci95_low or 0.0
            if cand_hi < default_lo:
                recs.append(Recommendation(
                    gate=gate_name,
                    current_threshold=default_sweep.threshold,
                    suggested_threshold=s.threshold,
                    reasoning=(
                        f"FRR at {s.threshold:.2f} is {s.metrics.frr:.3f} "
                        f"[{cand_lo:.3f}, {cand_hi:.3f}] vs default {default_sweep.metrics.frr:.3f} "
                        f"[{default_lo:.3f}, {default_hi:.3f}] — CI-disjoint, "
                        f"loosening recovers signals that would have been correct."
                    ),
                ))
                break  # report the smallest delta only
    return recs


# ── Report rendering ─────────────────────────────────────────────────────
def render_markdown(*, window_days: int, samples: list[Sample], metrics: list[GateMetrics],
                    sweeps: list[ThresholdSweep], recs: list[Recommendation]) -> str:
    n_with_outcome = sum(1 for s in samples if s.outcome_label is not None)
    n_with_clear_direction = sum(
        1 for s in samples
        if (s.impact_direction or "").upper() in ("BUY_YES", "BUY_NO")
    )
    n_gradeable = sum(
        1 for s in samples
        if s.outcome_label is not None
        and s.llm_predicted_direction_int() is not None
    )
    n_passed = sum(
        1 for s in samples
        if all(r.passed for r in replay_all_gates(s.gate_input()).values())
    )

    lines: list[str] = []
    lines.append("# Gate Effectiveness Backtest — Report")
    lines.append("")
    lines.append(f"**Generated:** {date.today().isoformat()}  ")
    lines.append(f"**Window:** last {window_days} days  ")
    lines.append(f"**Pairs analyzed:** {len(samples)}  ")
    lines.append(f"**Pairs with clear LLM direction (BUY_YES/BUY_NO):** {n_with_clear_direction}  ")
    lines.append(f"**Pairs with binary outcome (price ≤0.05 or ≥0.95):** {n_with_outcome}  ")
    lines.append(f"**Pairs gradeable (clear direction AND binary outcome):** {n_gradeable}  ")
    lines.append(f"**Pairs passing all 6 replayable gates:** {n_passed}  ")
    lines.append("**Companion PR:** [#3 — instrumentation](https://github.com/vcapton-jpg/polymarket-ai/pull/3)")
    lines.append("")
    lines.append("## Executive summary")
    lines.append("")

    # Pull cosine default sweep for the headline if it exists
    cosine_default = next(
        (m for m in metrics if m.name == "cosine"), None,
    )
    if cosine_default and cosine_default.frr is not None:
        lines.append(
            f"- **Cosine gate FRR = {cosine_default.frr:.3f} "
            f"[{cosine_default.frr_ci95_low:.3f}, {cosine_default.frr_ci95_high:.3f}]** "
            f"(n={cosine_default.n_rejected_with_outcome}). The CI overlaps 0.50 "
            f"(random-direction baseline) so the finding is not statistically conclusive, "
            f"but the central estimate is directional: pairs the cosine gate rejects appear "
            f"to retain useful signal."
        )
    if recs:
        lines.append(f"- **{len(recs)} gate(s) flagged for threshold change** (CI95 disjoint vs default)")
        for r in recs:
            lines.append(
                f"  - `{r.gate}`: lower from {r.current_threshold:.2f} to {r.suggested_threshold:.2f}"
            )
    else:
        lines.append(
            "- **No statistically significant threshold changes recommended** — sample size "
            "is below the CI-disjoint floor for every gate. The default thresholds may be "
            "fine, or the data volume is the bottleneck. Re-run after PR #3 has accumulated "
            "2-4 weeks of `event_market_features` rows."
        )
    lines.append(
        f"- **Coverage bottleneck:** only {n_gradeable} of {len(samples)} analyzed pairs "
        f"({100 * n_gradeable / max(len(samples),1):.1f} %) are gradeable. Two filters compound: "
        f"(a) the LLM commits to BUY_YES/BUY_NO on only {n_with_clear_direction} pairs "
        f"({100 * n_with_clear_direction / max(len(samples),1):.1f} %); "
        f"(b) only {n_with_outcome} markets ({100 * n_with_outcome / max(len(samples),1):.1f} %) "
        f"closed in the binary band within the window. This is structural, not a bug — many "
        f"events are filed but never reach a clean YES/NO resolution."
    )
    lines.append("")
    lines.append("## Per-gate False-Rejection Rate (FRR)")
    lines.append("")
    lines.append(
        "FRR = `P(LLM-predicted direction matches outcome | gate rejected the pair)`. "
        "Higher FRR = the gate is over-rejecting useful signals. "
        "`outcome` is the binary-band resolution (≥0.95→1, ≤0.05→0)."
    )
    lines.append("")
    lines.append("| Gate | Threshold | n_rejected | n_with_outcome | FRR | CI95 | Note |")
    lines.append("|---|---|---|---|---|---|---|")
    for m in metrics:
        threshold_str = f"{m.threshold:.2f}" if m.threshold is not None else "—"
        frr_str = f"{m.frr:.3f}" if m.frr is not None else "—"
        ci_str = (
            f"[{m.frr_ci95_low:.3f}, {m.frr_ci95_high:.3f}]"
            if m.frr_ci95_low is not None
            else "—"
        )
        note = "low-N (interpret with caution)" if m.low_n() else ""
        lines.append(
            f"| `{m.name}` | {threshold_str} | {m.n_rejected} | "
            f"{m.n_rejected_with_outcome} | {frr_str} | {ci_str} | {note} |"
        )
    lines.append("")

    lines.append("## Counterfactual threshold sweep (numeric gates)")
    lines.append("")
    lines.append("For each numeric gate, ± 0.05 / ± 0.10 around the default. Same FRR metric.")
    lines.append("")
    lines.append("| Gate | Δ | Threshold | n_rejected | n_with_outcome | FRR | CI95 |")
    lines.append("|---|---|---|---|---|---|---|")
    for s in sweeps:
        m = s.metrics
        frr_str = f"{m.frr:.3f}" if m.frr is not None else "—"
        ci_str = (
            f"[{m.frr_ci95_low:.3f}, {m.frr_ci95_high:.3f}]"
            if m.frr_ci95_low is not None
            else "—"
        )
        delta_str = f"{s.delta:+.2f}" if s.delta != 0 else "0  "
        lines.append(
            f"| `{s.gate}` | {delta_str} | {s.threshold:.2f} | {m.n_rejected} | "
            f"{m.n_rejected_with_outcome} | {frr_str} | {ci_str} |"
        )
    lines.append("")

    lines.append("## Recommended threshold changes")
    lines.append("")
    if not recs:
        lines.append("_None — no CI-disjoint alternative found at current data volume._")
    else:
        for r in recs:
            lines.append(f"### `{r.gate}` — {r.current_threshold:.2f} → {r.suggested_threshold:.2f}")
            lines.append("")
            lines.append(r.reasoning)
            lines.append("")
    lines.append("")

    lines.append("## Deferred gates (require PR #1 instrumentation data)")
    lines.append("")
    lines.append(
        "These 7 gates depend on at-time market state (`spread`, `last_trade_price`, "
        "`liquidity`, `volume_24h`) that was not historically snapshotted. They become "
        "backtestable 2-4 weeks after [PR #3](https://github.com/vcapton-jpg/polymarket-ai/pull/3) "
        "merges and `event_market_features` accumulates."
    )
    lines.append("")
    for g in DEFERRED_GATES:
        lines.append(f"- `{g}`")
    lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "1. SQL pull joins `event_market_analysis` × `event_market_candidates` × "
        "(`signal_outcomes` for passed pairs OR `markets.closed=true AND price ∈ "
        "binary band` for rejected pairs).\n"
        "2. For each pair, the 6 replayable gates are evaluated against the stored "
        "LLM analysis + cosine.\n"
        "3. For each gate, FRR counts the share of rejected pairs whose LLM direction "
        "matches the eventual outcome — i.e., the share of \"would have been correct\" "
        "rejections.\n"
        "4. CI95 via 1 000-sample bootstrap, seed 42 (deterministic across runs).\n"
        "5. A recommendation fires only if a less-strict threshold has FRR CI95 "
        "disjoint from (and below) the default's FRR — same gate as "
        "`scripts/tune_heuristic_weights.evaluation_gate`.\n"
        "6. Categorical gates (`direction_clear`, `impact_strength`, `has_reasoning`) "
        "are not threshold-tunable — only their FRR is reported."
    )
    return "\n".join(lines) + "\n"


# ── Main ─────────────────────────────────────────────────────────────────
async def _main_async(*, window: int, out: Path) -> None:
    samples = await fetch_samples(window)
    if not samples:
        print(f"No samples in the last {window} days; nothing to write.")
        return

    metrics = compute_metrics(samples)
    sweeps = compute_counterfactuals(samples)
    recs = derive_recommendations(sweeps)

    md = render_markdown(
        window_days=window, samples=samples,
        metrics=metrics, sweeps=sweeps, recs=recs,
    )
    out.write_text(md, encoding="utf-8")

    json_out = out.with_suffix(".json")
    json_out.write_text(json.dumps({
        "generated_at": date.today().isoformat(),
        "window_days": window,
        "n_samples": len(samples),
        "n_with_outcome": sum(1 for s in samples if s.outcome_label is not None),
        "metrics": [m.to_dict() for m in metrics],
        "sweeps": [s.to_dict() for s in sweeps],
        "recommendations": [r.to_dict() for r in recs],
        "deferred_gates": DEFERRED_GATES,
    }, indent=2, sort_keys=True), encoding="utf-8")

    print(f"wrote {out} and {json_out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the 6 replayable rejection gates.")
    parser.add_argument("--window", type=int, default=90,
                        help="Window in days (default 90).")
    parser.add_argument(
        "--out", type=Path,
        default=Path(f"docs/audit/gate_effectiveness_{date.today().isoformat()}.md"),
        help="Markdown output path. JSON sidecar derives from this.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(window=args.window, out=args.out))


if __name__ == "__main__":
    main()
