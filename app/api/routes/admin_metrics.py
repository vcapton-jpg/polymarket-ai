"""Admin metrics — aggregated read endpoints over signal_predictions.

These endpoints power the CLI (`scripts/report_metrics.py`) and, later, an
admin FE page. Read-only, expensive aggregations are server-side so the client
stays dumb.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps.admin import require_admin
from app.api.schemas.admin_metrics import VariantAggregate, VariantsResponse
from app.db.database import get_session_factory
from app.db.models import SignalPrediction
from app.measurement.metrics import wilson_ci95

router = APIRouter(prefix="/admin/metrics", tags=["admin-metrics"])


def _window_to_cutoff(window: str, now: datetime) -> datetime:
    """'30d' -> now - 30 days. Accept plain digits + 'd' suffix only (YAGNI)."""
    if not window.endswith("d"):
        raise ValueError(f"unsupported window: {window!r}")
    try:
        days = int(window[:-1])
    except ValueError as e:
        raise ValueError(f"unsupported window: {window!r}") from e
    return now - timedelta(days=days)


@router.get("/variants", response_model=VariantsResponse)
async def get_variants(
    window: str = Query("30d"),
    _admin=Depends(require_admin),
) -> VariantsResponse:
    now = datetime.now(timezone.utc)
    cutoff = _window_to_cutoff(window, now)

    factory = get_session_factory()
    async with factory() as s:
        variants_stmt = (
            select(SignalPrediction.variant)
            .where(SignalPrediction.created_at >= cutoff)
            .group_by(SignalPrediction.variant)
        )
        names = [r[0] for r in (await s.execute(variants_stmt)).all()]

        out: list[VariantAggregate] = []
        for name in names:
            rows = (
                await s.execute(
                    select(
                        SignalPrediction.direction_correct,
                        SignalPrediction.brier_score,
                        SignalPrediction.simulated_pnl_eur,
                        SignalPrediction.predicted_direction,
                        SignalPrediction.resolved_at,
                    ).where(
                        SignalPrediction.variant == name,
                        SignalPrediction.created_at >= cutoff,
                    )
                )
            ).all()

            n_coverage = len(rows)
            resolved = [r for r in rows if r.resolved_at is not None and r.predicted_direction is not None]
            n = len(resolved)
            if n == 0:
                out.append(VariantAggregate(
                    variant=name, n=0, n_coverage=n_coverage,
                    winrate=None, winrate_ci95_low=None, winrate_ci95_high=None,
                    brier=None, brier_n=0,
                    pnl_per_trade_eur=None, pnl_total_eur=None,
                ))
                continue

            wins = sum(1 for r in resolved if r.direction_correct)
            winrate = wins / n
            lo, hi = wilson_ci95(n=n, k=wins)

            briers = [float(r.brier_score) for r in resolved if r.brier_score is not None]
            pnls = [float(r.simulated_pnl_eur) for r in resolved if r.simulated_pnl_eur is not None]

            out.append(VariantAggregate(
                variant=name, n=n, n_coverage=n_coverage,
                winrate=winrate, winrate_ci95_low=lo, winrate_ci95_high=hi,
                brier=(mean(briers) if briers else None),
                brier_n=len(briers),
                pnl_per_trade_eur=(mean(pnls) if pnls else None),
                pnl_total_eur=(sum(pnls) if pnls else None),
            ))

        out.sort(key=lambda v: (0 if v.variant == "signal" else 1, v.variant))

        return VariantsResponse(
            window=window,
            as_of=now.isoformat(),
            variants=out,
        )
