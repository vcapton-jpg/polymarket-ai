"""Pure-function replay of the 6 backtestable rejection gates.

Mirrors the prod gates in `app.signal.signal_builder.SignalBuilder.build_signal`
([signal_builder.py:122-167](../signal/signal_builder.py)). The other 7
production gates depend on at-time market state (`spread`, `last_trade_price`,
`liquidity`, `volume_24h`) that was not historically snapshotted —
backtesting them requires the `event_market_features` instrumentation
shipped in the companion PR.

Replay is a *mirror* of prod, not a re-import: a future change in
prod must trigger a test failure here so the offline backtest report
doesn't silently drift. Pinned by `tests/unit/scoring/test_gate_replay.py`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GateInput:
    """Input row for replay. All fields are optional so a single dataclass
    matches every gate's signature without manual plumbing.
    """
    cosine_score: float | None = None
    impact_direction: str | None = None
    ambiguity_score: float | None = None
    specificity_score: float | None = None
    impact_strength: float | None = None
    reasoning: str | None = None


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reason: str | None = None


# ── 1. cosine — mirrors signal_builder.py:122-127 ────────────────────────
def gate_cosine(inp: GateInput, *, threshold: float = 0.52) -> GateResult:
    if inp.cosine_score is None:
        return GateResult(passed=True)
    if inp.cosine_score < threshold:
        return GateResult(
            passed=False,
            reason=f"cosine {inp.cosine_score:.3f} < {threshold:.2f}",
        )
    return GateResult(passed=True)


# ── 2. direction_clear — mirrors signal_builder.py:135-138 ───────────────
def gate_direction_clear(inp: GateInput) -> GateResult:
    direction = (inp.impact_direction or "").upper()
    if direction in ("NEUTRAL", "UNCLEAR", ""):
        return GateResult(
            passed=False,
            reason=f"direction={direction or 'MISSING'}",
        )
    return GateResult(passed=True)


# ── 3. ambiguity — mirrors signal_builder.py:140-143 ─────────────────────
def gate_ambiguity(inp: GateInput, *, threshold: float = 0.80) -> GateResult:
    if inp.ambiguity_score is None:
        return GateResult(passed=True)
    if inp.ambiguity_score > threshold:
        return GateResult(
            passed=False,
            reason=f"ambiguity {inp.ambiguity_score:.2f} > {threshold:.2f}",
        )
    return GateResult(passed=True)


# ── 4. specificity — mirrors signal_builder.py:145-148 ───────────────────
def gate_specificity(inp: GateInput, *, threshold: float = 0.40) -> GateResult:
    if inp.specificity_score is None:
        return GateResult(passed=True)
    if inp.specificity_score < threshold:
        return GateResult(
            passed=False,
            reason=f"specificity {inp.specificity_score:.2f} < {threshold:.2f}",
        )
    return GateResult(passed=True)


# ── 5. impact_strength — mirrors signal_builder.py:150-153 ───────────────
def gate_impact_strength(inp: GateInput) -> GateResult:
    if inp.impact_strength is None or float(inp.impact_strength) == 0:
        return GateResult(passed=False, reason="no impact_strength")
    return GateResult(passed=True)


# ── 6. has_reasoning — mirrors signal_builder.py:300-307 ─────────────────
def gate_has_reasoning(inp: GateInput) -> GateResult:
    if not inp.reasoning or not inp.reasoning.strip():
        return GateResult(passed=False, reason="missing reasoning")
    return GateResult(passed=True)


# ── Aggregator ────────────────────────────────────────────────────────────
def replay_all_gates(
    inp: GateInput,
    *,
    cosine_threshold: float = 0.52,
    ambiguity_threshold: float = 0.80,
    specificity_threshold: float = 0.40,
) -> dict[str, GateResult]:
    """Run all 6 replayable gates against one input. Returns a dict of
    per-gate `GateResult`. Failures DO NOT short-circuit: every gate runs
    so the backtest can attribute rejection blame correctly when multiple
    gates would have fired on the same pair.
    """
    return {
        "cosine": gate_cosine(inp, threshold=cosine_threshold),
        "direction_clear": gate_direction_clear(inp),
        "ambiguity": gate_ambiguity(inp, threshold=ambiguity_threshold),
        "specificity": gate_specificity(inp, threshold=specificity_threshold),
        "impact_strength": gate_impact_strength(inp),
        "has_reasoning": gate_has_reasoning(inp),
    }
