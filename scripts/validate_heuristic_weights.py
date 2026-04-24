"""Offline validation: join SignalPrediction × SignalOutcome at a given horizon,
compute Brier (binarised) / simulated P&L / Wilson-CI95 per variant, and emit a
markdown report suitable for committing to docs/audit/.

CLI:
    python -m scripts.validate_heuristic_weights \\
        --horizon t1h \\
        --out docs/audit/heuristic_validation_report_YYYY-MM-DD.md

Why a script, not a FastAPI endpoint: one-shot, human-triggered, audited via
git history. The measurement infra has no scheduler for this.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from sqlalchemy import text

from app.db.database import async_session_factory
from app.measurement.metrics import (
    brier_from_outcome,
    simulated_pnl_eur,
    wilson_ci95,
)


ALLOWED_HORIZONS = ("t15min", "t1h", "t24h")


@dataclass(frozen=True)
class JoinedRow:
    variant: str
    predicted_probability: float
    predicted_direction: str | None
    price_t1h: float   # reused for whichever horizon was selected


def _binarise(price: float) -> int | None:
    """Mirror app.measurement.pipeline._binary_from_resolved."""
    if price >= 0.95:
        return 1
    if price <= 0.05:
        return 0
    return None


def aggregate_variant_metrics(rows: Iterable[JoinedRow]) -> dict[str, dict]:
    """Compute per-variant metrics from a batch of JoinedRow."""
    by_variant: dict[str, list[JoinedRow]] = {}
    for r in rows:
        by_variant.setdefault(r.variant, []).append(r)

    out: dict[str, dict] = {}
    for variant, batch in by_variant.items():
        n = len(batch)
        briers: list[float] = []
        pnls: list[float] = []
        hits: list[int] = []
        for r in batch:
            bin_outcome = _binarise(r.price_t1h)
            if bin_outcome is not None:
                b = brier_from_outcome(r.predicted_probability, bin_outcome)
                if b is not None:
                    briers.append(b)
                if r.predicted_direction in ("BUY_YES", "BUY_NO"):
                    correct = (
                        (r.predicted_direction == "BUY_YES" and bin_outcome == 1)
                        or (r.predicted_direction == "BUY_NO" and bin_outcome == 0)
                    )
                    hits.append(1 if correct else 0)
            if r.predicted_direction in ("BUY_YES", "BUY_NO"):
                pnls.append(simulated_pnl_eur(
                    direction=r.predicted_direction,
                    probability=r.predicted_probability,
                    price_resolved=r.price_t1h,
                ))

        brier_mean = sum(briers) / len(briers) if briers else float("nan")
        pnl_mean = sum(pnls) / len(pnls) if pnls else 0.0
        hit_rate = sum(hits) / len(hits) if hits else float("nan")
        hit_ci_low, hit_ci_high = wilson_ci95(len(hits), sum(hits)) if hits else (0.0, 1.0)

        def _ci(values: list[float]) -> tuple[float, float]:
            if len(values) < 2:
                return (float("nan"), float("nan"))
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
            se = (var / len(values)) ** 0.5
            return (mean - 1.96 * se, mean + 1.96 * se)

        out[variant] = {
            "n": n,
            "n_brier_defined": len(briers),
            "brier_mean": brier_mean,
            "brier_ci95": _ci(briers),
            "pnl_mean": pnl_mean,
            "pnl_ci95": _ci(pnls),
            "hit_rate": hit_rate,
            "hit_rate_ci95": (hit_ci_low, hit_ci_high),
        }
    return out


def build_markdown_report(metrics: dict[str, dict], *, horizon: str, generated_at: str) -> str:
    """Render the metrics dict as a committable markdown table."""
    header = (
        f"# Heuristic Validation Report — horizon={horizon}\n\n"
        f"Generated: {generated_at}\n\n"
        "| variant | n | n_brier_defined | brier_mean | brier_ci95 | pnl_mean | pnl_ci95 | hit_rate | hit_rate_ci95 |\n"
        "|---|---|---|---|---|---|---|---|---|\n"
    )
    lines = []
    ordered = sorted(
        metrics.keys(),
        key=lambda v: (not v.startswith("heuristic_"), v),
    )
    for variant in ordered:
        m = metrics[variant]
        lines.append(
            f"| `{variant}` | {m['n']} | {m['n_brier_defined']} | "
            f"{m['brier_mean']:.4f} | "
            f"[{m['brier_ci95'][0]:.4f}, {m['brier_ci95'][1]:.4f}] | "
            f"€{m['pnl_mean']:.3f} | "
            f"[€{m['pnl_ci95'][0]:.3f}, €{m['pnl_ci95'][1]:.3f}] | "
            f"{m['hit_rate']:.3f} | "
            f"[{m['hit_rate_ci95'][0]:.3f}, {m['hit_rate_ci95'][1]:.3f}] |"
        )
    return header + "\n".join(lines) + "\n"


async def _fetch_joined_rows(horizon: str) -> list[JoinedRow]:
    col = f"price_{horizon}"
    sql = text(
        f"""SELECT sp.variant, sp.predicted_probability, sp.predicted_direction,
                   so.{col} AS price_horizon
            FROM signal_predictions sp
            JOIN signal_outcomes so ON sp.signal_id = so.signal_id
            WHERE so.{col} IS NOT NULL
              AND sp.predicted_probability IS NOT NULL"""
    )
    async with async_session_factory() as s:
        rs = await s.execute(sql)
        return [
            JoinedRow(
                variant=row[0],
                predicted_probability=float(row[1]),
                predicted_direction=row[2],
                price_t1h=float(row[3]),
            )
            for row in rs.all()
        ]


async def _main_async(*, horizon: str, out_path: str) -> None:
    rows = await _fetch_joined_rows(horizon)
    metrics = aggregate_variant_metrics(rows)
    md = build_markdown_report(metrics, horizon=horizon, generated_at=str(date.today()))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"wrote {out_path} ({len(rows)} joined rows, {len(metrics)} variants)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate heuristic weights vs baselines.")
    parser.add_argument(
        "--horizon",
        choices=ALLOWED_HORIZONS,
        default="t1h",
        help="Which outcome horizon to validate against (default: t1h).",
    )
    parser.add_argument(
        "--out",
        default=f"docs/audit/heuristic_validation_report_{date.today().isoformat()}.md",
        help="Output markdown report path.",
    )
    args = parser.parse_args()
    asyncio.run(_main_async(horizon=args.horizon, out_path=args.out))


if __name__ == "__main__":
    main()
