"""LLM calibration report — LEVIER-2 decision support. Read-only.

H+24 (2026-05-19) flagged that LEVIER-2 (recalibration, shrink 0.55)
has the T-001 profile — it rejects signals that would have been
slightly profitable (rtp_avoided +1.83 %, n=22). Before the H+72
decision we want the real calibration picture, not one number:

  * Brier score   — mean (predicted − actual)². Lower = better.
  * Reliability    — 10 prediction buckets, predicted mean vs realised
                     mean. Shows WHERE the model is over/under-confident.
  * Optimal shrink — the closed-form s* that minimises the Brier of
                     `calibrated = 0.5 + (pred − 0.5)·s`. Tells us
                     whether 0.55 is right, too aggressive, or whether
                     recalibration helps at all.

Ground truth: we don't have binary resolution for most signals (<24 h
markets rarely settle), so `actual` is proxied by the market price
after the signal (price_t24h, falling back to price_t1h) — the same
proxy the RTP estimator uses. Imperfect but consistent.

USAGE
-----
    ssh foresight 'docker compose -f /opt/foresight/docker-compose.yml \\
      exec -T app python -m scripts.shadow.calibration_report \\
      --window-days 14'

Read-only — only SELECTs.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ──────────────────────────────────────────────────────────────────────
# Pure stats — unit-tested without a DB.
# ──────────────────────────────────────────────────────────────────────


def brier(pairs: list[tuple[float, float]]) -> float | None:
    """Mean squared error between predicted and actual probability."""
    if not pairs:
        return None
    return sum((p - a) ** 2 for p, a in pairs) / len(pairs)


def optimal_shrink(pairs: list[tuple[float, float]]) -> float | None:
    """Closed-form s* minimising Σ(0.5 + (p−0.5)s − a)².

    Derivative = 0  ⟹  s* = Σ(p−0.5)(a−0.5) / Σ(p−0.5)².
    s* = 1   → model already calibrated (no shrink needed)
    s* < 1   → model over-confident (shrink toward 0.5 helps)
    s* > 1   → model under-confident (should amplify, not shrink)
    s* ≤ 0   → predictions are noise / anti-correlated
    """
    num = sum((p - 0.5) * (a - 0.5) for p, a in pairs)
    den = sum((p - 0.5) ** 2 for p, a in pairs)
    if den == 0:
        return None
    return num / den


def reliability_buckets(
    pairs: list[tuple[float, float]], n_buckets: int = 10
) -> list[dict]:
    """Group by predicted-probability decile; report predicted vs
    realised mean per bucket (the reliability-diagram data)."""
    buckets: list[list[tuple[float, float]]] = [[] for _ in range(n_buckets)]
    for p, a in pairs:
        idx = min(int(p * n_buckets), n_buckets - 1)
        buckets[idx].append((p, a))
    out: list[dict] = []
    for i, b in enumerate(buckets):
        if not b:
            continue
        lo, hi = i / n_buckets, (i + 1) / n_buckets
        out.append(
            {
                "bucket": f"{lo:.1f}-{hi:.1f}",
                "n": len(b),
                "pred_mean": round(sum(p for p, _ in b) / len(b), 3),
                "actual_mean": round(sum(a for _, a in b) / len(b), 3),
                "gap": round(
                    sum(p for p, _ in b) / len(b)
                    - sum(a for _, a in b) / len(b),
                    3,
                ),
            }
        )
    return out


# ──────────────────────────────────────────────────────────────────────
# Data
# ──────────────────────────────────────────────────────────────────────


async def _fetch_pairs(window_days: int) -> list[tuple[float, float]]:
    from sqlalchemy import text

    from app.db.database import get_session_factory

    sql = text(
        f"""
        SELECT
            s.implied_yes_probability AS pred,
            COALESCE(so.price_t24h, so.price_t1h) AS actual
        FROM signals s
        JOIN signal_outcomes so ON so.signal_id = s.id
        WHERE s.created_at > NOW() - INTERVAL '{int(window_days)} days'
          AND s.implied_yes_probability IS NOT NULL
          AND COALESCE(so.price_t24h, so.price_t1h) IS NOT NULL
        """
    )
    SessionLocal = get_session_factory()
    async with SessionLocal() as session:
        rows = (await session.execute(sql)).mappings().all()
    return [(float(r["pred"]), float(r["actual"])) for r in rows]


# ──────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────


async def main_async(window_days: int, current_shrink: float) -> int:
    pairs = await _fetch_pairs(window_days)
    n = len(pairs)
    print(f"# LLM calibration report — {window_days} d, n={n}")
    print()
    if n < 10:
        print(f"⏳ Only {n} labelled predictions — too few to calibrate. "
              "implied_yes_probability has been captured since 2026-05-13; "
              "wait for more.")
        return 1

    raw_brier = brier(pairs)
    s_star = optimal_shrink(pairs)

    # Brier of the currently-shipped shrink (0.55) for comparison.
    def _shrunk(s: float) -> list[tuple[float, float]]:
        return [(0.5 + (p - 0.5) * s, a) for p, a in pairs]

    cur_brier = brier(_shrunk(current_shrink))
    opt_brier = brier(_shrunk(s_star)) if s_star is not None else None

    print("## Headline")
    print()
    print(f"- Raw Brier (no recalibration):       **{raw_brier:.4f}**")
    print(f"- Brier @ shipped shrink {current_shrink}:      **{cur_brier:.4f}**")
    if s_star is not None:
        print(f"- Optimal shrink s* (closed-form):    **{s_star:.3f}**")
        print(f"- Brier @ optimal shrink:             **{opt_brier:.4f}**")
        verdict = (
            "model already ~calibrated — recalibration barely helps"
            if 0.85 <= s_star <= 1.15
            else "model OVER-confident — shrink toward 0.5 helps"
            if 0 < s_star < 0.85
            else "model UNDER-confident — shrinking is WRONG, it should amplify"
            if s_star > 1.15
            else "predictions uninformative / anti-correlated — recalibration can't save it"
        )
        print(f"- **Verdict: {verdict}**")
        improvement = (
            (raw_brier - opt_brier) / raw_brier * 100
            if raw_brier and opt_brier is not None and raw_brier > 0
            else 0.0
        )
        print(f"- Max Brier improvement from recalibration: {improvement:.1f} %")
    print()
    print("## Reliability diagram (predicted decile → realised mean)")
    print()
    print("| bucket | n | predicted | realised | gap |")
    print("|---|---:|---:|---:|---:|")
    for r in reliability_buckets(pairs):
        print(
            f"| {r['bucket']} | {r['n']} | {r['pred_mean']} | "
            f"{r['actual_mean']} | {r['gap']:+.3f} |"
        )
    print()
    print("---")
    print(
        "**How to use at H+72:** if s* ≈ 0.55 the shipped LEVIER-2 value "
        "is right. If s* ≫ 0.55 the shrink is too aggressive (it's "
        "rejecting real edge — matches the rtp_avoided +1.83 % flag) → "
        "raise `llm_calibration_shrink`. If s* ≥ ~1 or the Brier barely "
        "moves, recalibration adds nothing → disable LEVIER-2 like T-001."
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--window-days", type=int, default=14)
    p.add_argument(
        "--current-shrink",
        type=float,
        default=0.55,
        help="The llm_calibration_shrink currently shipped (for comparison).",
    )
    args = p.parse_args()
    return asyncio.run(main_async(args.window_days, args.current_shrink))


if __name__ == "__main__":
    sys.exit(main())
