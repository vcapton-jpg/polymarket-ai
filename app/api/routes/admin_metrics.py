"""Admin metrics — aggregated read endpoints over signal_predictions.

These endpoints power the CLI (`scripts/report_metrics.py`) and, later, an
admin FE page. Read-only, expensive aggregations are server-side so the client
stays dumb.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps.admin import require_admin
from app.api.schemas.admin_metrics import (
    RollingPoint,
    RollingResponse,
    VariantAggregate,
    VariantsResponse,
)
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
    now = datetime.now(UTC)
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

        out.sort(key=lambda v: (0 if v.variant == "heuristic_v1" else 1, v.variant))

        return VariantsResponse(
            window=window,
            as_of=now.isoformat(),
            variants=out,
        )


@router.get("/variants/rolling", response_model=RollingResponse)
async def get_rolling(
    window: str = Query("30d"),
    step: str = Query("1d"),
    _admin=Depends(require_admin),
) -> RollingResponse:
    if step != "1d":
        # YAGNI — only 1d step for now.
        raise ValueError(f"unsupported step: {step!r}")

    now = datetime.now(UTC)
    cutoff = _window_to_cutoff(window, now)

    factory = get_session_factory()
    async with factory() as s:
        rows = (
            await s.execute(
                select(
                    SignalPrediction.variant,
                    SignalPrediction.resolved_at,
                    SignalPrediction.direction_correct,
                ).where(
                    SignalPrediction.resolved_at >= cutoff,
                    SignalPrediction.resolved_at.is_not(None),
                    SignalPrediction.predicted_direction.is_not(None),
                ).order_by(SignalPrediction.resolved_at)
            )
        ).all()

    # Group events by variant, emit one point per day with end-of-day
    # cumulative n + winrate.
    by_variant: dict[str, list[tuple[datetime, bool]]] = {}
    for v, ra, correct in rows:
        by_variant.setdefault(v, []).append((ra, bool(correct)))

    series: list[RollingPoint] = []
    for v, events in by_variant.items():
        events.sort(key=lambda t: t[0])
        agg: dict[str, tuple[int, int]] = {}
        n_run = 0
        w_run = 0
        for ra, correct in events:
            n_run += 1
            if correct:
                w_run += 1
            day = ra.date().isoformat()
            agg[day] = (n_run, w_run)  # overwrite; final value = end-of-day cumulative
        for day, (n_cum_d, w_cum_d) in sorted(agg.items()):
            series.append(RollingPoint(
                date=day,
                variant=v,
                n_cumulative=n_cum_d,
                winrate_cumulative=(w_cum_d / n_cum_d) if n_cum_d else None,
            ))

    return RollingResponse(window=window, step=step, series=series)
