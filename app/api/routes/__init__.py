"""API routes — all endpoints under /api."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import (
    AccuracyResponse,
    CostResponse,
    DashboardKpisResponse,
    EventListResponse,
    EventOut,
    HealthResponse,
    IngestionHealthResponse,
    MarketListResponse,
    MarketOut,
    PipelineStatusResponse,
    SimulatedPnlResponse,
    TrackRecordResponse,
)
from app.api.schemas_v2 import (
    SignalCardOut,
    SignalDetailOut,
    SignalListOut,
    SignalSourceOut,
)
from app.api.signal_mapper import (
    build_detailed_sources,
    derive_direction,
    to_signal_card,
    to_signal_detail,
)
from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import (
    Event,
    EventMarketAnalysis,
    EventNewsLink,
    LLMCostLog,
    Market,
    News,
    NewsClean,
    Signal,
    SignalOutcome,
)

settings = get_settings()
router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────
_EXPECTED_WORKERS = {"ingestion", "scoring", "markets", "outcomes"}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    import asyncio

    workers_status: dict[str, bool] = {}
    try:
        from app.workers.celery_app import celery_app as _celery

        ping_result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _celery.control.ping(timeout=2.0)
        )
        responded = {
            name.split("@")[0]
            for reply in (ping_result or [])
            for name in reply.keys()
        }
        for expected in _EXPECTED_WORKERS:
            workers_status[expected] = expected in responded
    except Exception:
        pass

    all_up = all(workers_status.get(w, False) for w in _EXPECTED_WORKERS) if workers_status else True
    return HealthResponse(
        status="healthy" if all_up else "degraded",
        version=settings.app_version,
        env=settings.env,
        workers=workers_status or None,
    )


# ── Signals ───────────────────────────────────────────────────────────
# Wire shape matches `frontend/src/types/signal.ts` 1:1 (camelCase + French
# labels). All translation/enrichment lives in `app.api.signal_mapper` so
# the React layer stays a dumb renderer.
@router.get("/signals", response_model=SignalListOut)
async def list_signals(
    category: Optional[str] = Query(
        None,
        description="V2 frontend category filter (geopolitics|politics|economics|crypto|sports|science).",
    ),
    bucket: Optional[str] = Query(
        None, description="Legacy bucket filter (pre-V2 clients)."
    ),
    # Default to the worker's `signal_score_threshold` so the public list
    # mirrors what the scorer considers "above-threshold". Below-threshold
    # signals are still persisted (signal_builder.py:206 _below_threshold
    # path) but are filtered out of the default response — clients can
    # opt back in by passing `?min_score=0` (debug) or `?min_score=N` for
    # any custom cutoff. Pre-fix this defaulted to 0, which leaked all
    # ~184 sub-threshold signals (40 % of historical) to the public UI.
    min_score: float = Query(
        default_factory=lambda: float(settings.signal_score_threshold),
        ge=0,
        le=100,
    ),
    direction: Optional[str] = Query(
        None, description="YES, NO, or legacy BUY_YES/BUY_NO."
    ),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    lo = settings.signal_tradeable_yes_min
    hi = settings.signal_tradeable_yes_max
    min_cos = settings.signal_min_cosine_score

    price_ok = (Signal.market_price_at_signal >= lo) & (Signal.market_price_at_signal <= hi)
    cosine_ok = (Signal.cosine_score >= min_cos) | (Signal.cosine_score.is_(None))

    query = (
        select(Signal)
        .options(selectinload(Signal.event), selectinload(Signal.market))
        .where(price_ok & cosine_ok)
        .order_by(desc(Signal.created_at))
    )

    # Accept both the V2 `category=` and the legacy `bucket=` query params.
    filter_bucket = bucket or category
    if filter_bucket:
        query = query.join(Event).where(Event.bucket == filter_bucket)
    if min_score > 0:
        query = query.where(Signal.signal_score >= min_score)
    if direction:
        # Frontend sends "YES"/"NO"; DB stores "BUY_YES"/"BUY_NO".
        # Accept both forms and collapse NO -> BUY_NO, YES -> BUY_YES.
        dir_norm = derive_direction(direction)
        db_direction = "BUY_NO" if dir_norm == "NO" else "BUY_YES"
        query = query.where(Signal.direction == db_direction)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    signals = result.scalars().all()

    # Bulk-fetch source counts so each card can render "N sources" without
    # paying for the full sources payload (the detail endpoint serves that).
    # Source count = number of EventNewsLink rows for the signal's event.
    # Single grouped query → O(1) round-trips regardless of page size.
    event_ids = [s.event_id for s in signals if s.event_id is not None]
    counts_by_event: dict[int, int] = {}
    if event_ids:
        counts_q = (
            select(EventNewsLink.event_id, func.count(EventNewsLink.clean_id))
            .where(EventNewsLink.event_id.in_(event_ids))
            .group_by(EventNewsLink.event_id)
        )
        counts_rows = (await db.execute(counts_q)).all()
        counts_by_event = {eid: int(cnt) for eid, cnt in counts_rows}

    return SignalListOut(
        signals=[
            to_signal_card(s, sources_count=counts_by_event.get(s.event_id, 0))
            for s in signals
        ],
        total=total,
    )


@router.get("/signals/{signal_id}", response_model=SignalDetailOut)
async def get_signal_detail(
    signal_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Signal)
        .options(
            selectinload(Signal.event).selectinload(Event.news_links)
            .selectinload(EventNewsLink.news_clean)
            .selectinload(NewsClean.news),
            selectinload(Signal.market),
            selectinload(Signal.outcome),
        )
        .where(Signal.id == signal_id)
    )
    result = await db.execute(query)
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    analysis_q = (
        select(EventMarketAnalysis)
        .where(
            EventMarketAnalysis.event_id == signal.event_id,
            EventMarketAnalysis.market_id == signal.market_id,
        )
        .limit(1)
    )
    analysis = (await db.execute(analysis_q)).scalar_one_or_none()
    news_links = signal.event.news_links if signal.event else []

    return to_signal_detail(signal, analysis, news_links)


@router.get("/signals/{signal_id}/sources", response_model=list[SignalSourceOut])
async def get_signal_sources(
    signal_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    query = (
        select(Signal)
        .options(
            selectinload(Signal.event).selectinload(Event.news_links)
            .selectinload(EventNewsLink.news_clean)
            .selectinload(NewsClean.news),
        )
        .where(Signal.id == signal_id)
    )
    signal = (await db.execute(query)).scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    news_links = signal.event.news_links if signal.event else []
    return build_detailed_sources(news_links)


# ── Markets ───────────────────────────────────────────────────────────
@router.get("/markets", response_model=MarketListResponse)
async def list_markets(
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(Market)
    if active_only:
        query = query.where(Market.active.is_(True), Market.closed.is_(False))
    if category:
        query = query.where(Market.category == category)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(desc(Market.updated_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    markets = result.scalars().all()

    return MarketListResponse(
        markets=[MarketOut.model_validate(m) for m in markets],
        total=total,
    )


# ── Events ────────────────────────────────────────────────────────────
@router.get("/events", response_model=EventListResponse)
async def list_events(
    bucket: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    query = select(Event).order_by(desc(Event.first_seen))
    if bucket:
        query = query.where(Event.bucket == bucket)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    events = result.scalars().all()

    return EventListResponse(
        events=[EventOut.model_validate(e) for e in events],
        total=total,
    )


# ── Analytics ─────────────────────────────────────────────────────────
@router.get("/analytics/accuracy", response_model=AccuracyResponse)
async def get_signal_accuracy(db: AsyncSession = Depends(get_db_session)):
    total_q = select(func.count()).select_from(Signal)
    total = (await db.execute(total_q)).scalar() or 0

    resolved_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label.is_not(None))
    )
    resolved = (await db.execute(resolved_q)).scalar() or 0

    correct_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label == 1)
    )
    correct = (await db.execute(correct_q)).scalar() or 0

    accuracy_pct = (correct / resolved * 100) if resolved > 0 else None

    by_bucket_q = (
        select(
            Event.bucket,
            func.count(Signal.id).label("total"),
            func.count(SignalOutcome.outcome_label).label("resolved"),
            func.sum(
                func.cast(SignalOutcome.outcome_label == 1, Integer)
            ).label("correct"),
        )
        .join(Signal, Signal.event_id == Event.id)
        .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(Event.bucket.is_not(None))
        .group_by(Event.bucket)
    )
    bucket_rows = (await db.execute(by_bucket_q)).all()
    by_bucket = {}
    for row in bucket_rows:
        bkt = row[0] or "other"
        t, r, c = row[1], row[2], row[3] or 0
        by_bucket[bkt] = {
            "total": t,
            "resolved": r,
            "correct": c,
            "accuracy_pct": round(c / r * 100, 1) if r > 0 else None,
        }

    return AccuracyResponse(
        total_signals=total,
        resolved_signals=resolved,
        correct_signals=correct,
        accuracy_pct=accuracy_pct,
        by_bucket=by_bucket,
    )


@router.get("/analytics/costs", response_model=CostResponse)
async def get_llm_costs(db: AsyncSession = Depends(get_db_session)):
    total_q = select(
        func.coalesce(func.sum(LLMCostLog.cost_usd), 0),
        func.count(),
    ).select_from(LLMCostLog)
    row = (await db.execute(total_q)).one()
    total_cost = float(row[0])
    total_calls = row[1]

    daily_q = (
        select(
            func.date_trunc("day", LLMCostLog.called_at).label("day"),
            LLMCostLog.call_type,
            func.sum(LLMCostLog.cost_usd).label("cost"),
            func.count().label("calls"),
        )
        .group_by("day", LLMCostLog.call_type)
        .order_by(desc("day"))
        .limit(30)
    )
    daily_rows = (await db.execute(daily_q)).all()
    by_day = [
        {
            "day": str(r.day.date()) if r.day else None,
            "call_type": r.call_type,
            "cost_usd": float(r.cost),
            "calls": r.calls,
        }
        for r in daily_rows
    ]

    return CostResponse(
        total_cost_usd=total_cost,
        total_calls=total_calls,
        by_day=by_day,
    )


# ── Ingestion health ─────────────────────────────────────────────────
@router.get("/analytics/ingestion", response_model=IngestionHealthResponse)
async def get_ingestion_health(db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    q = (
        select(
            News.source_name,
            News.source_tier,
            func.count().label("count_24h"),
            func.percentile_cont(0.5)
            .within_group(News.ingestion_lag_seconds)
            .label("median_lag"),
        )
        .where(News.ingestion_date > cutoff)
        .group_by(News.source_name, News.source_tier)
        .order_by(News.source_tier)
    )
    rows = (await db.execute(q)).all()

    sources = [
        {
            "source_name": r.source_name,
            "tier": r.source_tier,
            "articles_24h": r.count_24h,
            "median_lag_seconds": float(r.median_lag) if r.median_lag else None,
        }
        for r in rows
    ]

    tier1_lags = [
        s["median_lag_seconds"] for s in sources
        if s["tier"] == 1 and s["median_lag_seconds"] is not None
    ]
    tier1_median = (
        sorted(tier1_lags)[len(tier1_lags) // 2] if tier1_lags else None
    )

    return IngestionHealthResponse(
        sources=sources,
        tier1_median_lag_seconds=tier1_median,
        alert=tier1_median is not None and tier1_median > settings.tier1_lag_alert_seconds,
    )


# ── Pipeline status ──────────────────────────────────────────────────
@router.get("/pipeline/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(db: AsyncSession = Depends(get_db_session)):
    import asyncio

    last_article = (
        await db.execute(
            select(func.max(News.ingestion_date))
        )
    ).scalar()

    last_event = (
        await db.execute(
            select(func.max(Event.last_seen))
        )
    ).scalar()

    last_signal = (
        await db.execute(
            select(func.max(Signal.created_at))
        )
    ).scalar()

    events_pending = (
        await db.execute(
            select(func.count())
            .select_from(Event)
            .where(Event.processing_status.in_(["pending", "new", "candidates_found", "no_candidates"]))
        )
    ).scalar() or 0

    active_workers = 0
    try:
        from app.workers.celery_app import celery_app as _celery

        ping_result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _celery.control.ping(timeout=2.0)
        )
        active_workers = len(ping_result or [])
    except Exception:
        pass

    return PipelineStatusResponse(
        last_article_ingested=last_article,
        last_event_created=last_event,
        last_signal_created=last_signal,
        events_pending=events_pending,
        active_workers=active_workers,
    )


# ── Simulated P&L ────────────────────────────────────────────────────
@router.get("/analytics/simulated-pnl", response_model=SimulatedPnlResponse)
async def get_simulated_pnl(
    min_score: float = Query(60, ge=0, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    """Calculate retroactive P&L: if you had followed every signal at min_score+,
    buying YES/NO at signal price and selling at resolved price."""
    from sqlalchemy.orm import selectinload

    query = (
        select(Signal)
        .options(selectinload(Signal.outcome), selectinload(Signal.event))
        .where(Signal.signal_score >= min_score)
        .order_by(desc(Signal.created_at))
    )
    result = await db.execute(query)
    all_signals = result.scalars().all()

    total = len(all_signals)
    wins, losses = 0, 0
    win_moves, loss_moves = [], []
    best = None
    worst = None
    by_direction: dict[str, dict] = {}
    by_tier: dict[str, dict] = {}

    for s in all_signals:
        o = s.outcome
        if not o or o.price_resolved is None or s.market_price_at_signal is None:
            continue

        entry = float(s.market_price_at_signal)
        resolved = float(o.price_resolved)
        direction = s.direction or "BUY_YES"

        if "YES" in direction:
            pnl = resolved - entry
        else:
            pnl = (1.0 - resolved) - (1.0 - entry)

        pnl_pct = (pnl / max(entry, 0.01)) * 100
        is_win = pnl > 0

        if is_win:
            wins += 1
            win_moves.append(pnl_pct)
        else:
            losses += 1
            loss_moves.append(pnl_pct)

        sig_data = {
            "signal_id": s.id,
            "direction": direction,
            "entry_price": entry,
            "resolved_price": resolved,
            "pnl_pct": round(pnl_pct, 2),
            "event_title": s.event.event_title if s.event else None,
            "score": float(s.signal_score),
        }

        if best is None or pnl_pct > best["pnl_pct"]:
            best = sig_data
        if worst is None or pnl_pct < worst["pnl_pct"]:
            worst = sig_data

        d_key = direction
        if d_key not in by_direction:
            by_direction[d_key] = {"wins": 0, "losses": 0}
        by_direction[d_key]["wins" if is_win else "losses"] += 1

        if float(s.signal_score) >= 90:
            tier = "90+"
        elif float(s.signal_score) >= 75:
            tier = "75-89"
        elif float(s.signal_score) >= 60:
            tier = "60-74"
        else:
            tier = "<60"
        if tier not in by_tier:
            by_tier[tier] = {"wins": 0, "losses": 0}
        by_tier[tier]["wins" if is_win else "losses"] += 1

    resolved_total = wins + losses
    return SimulatedPnlResponse(
        total_signals=total,
        resolved_signals=resolved_total,
        simulated_pnl_pct=round(sum(win_moves) + sum(loss_moves), 2) if resolved_total > 0 else None,
        win_rate=round(wins / resolved_total * 100, 1) if resolved_total > 0 else None,
        wins=wins,
        losses=losses,
        avg_win_move_pct=round(sum(win_moves) / len(win_moves), 2) if win_moves else None,
        avg_loss_move_pct=round(sum(loss_moves) / len(loss_moves), 2) if loss_moves else None,
        best_signal=best,
        worst_signal=worst,
        by_direction=by_direction,
        by_score_tier=by_tier,
    )


# ── Dashboard KPIs (real, not hardcoded) ──────────────────────────────
@router.get("/analytics/dashboard-kpis", response_model=DashboardKpisResponse)
async def get_dashboard_kpis(db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total = (await db.execute(select(func.count()).select_from(Signal))).scalar() or 0
    signals_today = (
        await db.execute(
            select(func.count()).select_from(Signal).where(Signal.created_at >= today_start)
        )
    ).scalar() or 0

    resolved_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label.is_not(None))
    )
    resolved = (await db.execute(resolved_q)).scalar() or 0

    correct_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label == 1)
    )
    wins = (await db.execute(correct_q)).scalar() or 0
    losses = resolved - wins

    avg_score_val = (
        await db.execute(select(func.avg(Signal.signal_score)))
    ).scalar()

    best_signal_q = (
        select(Signal)
        .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(SignalOutcome.direction_correct.is_(True))
        .order_by(desc(Signal.signal_score))
        .limit(1)
    )
    best_sig = (await db.execute(best_signal_q)).scalar_one_or_none()
    best_data = None
    if best_sig:
        best_data = {
            "signal_id": best_sig.id,
            "score": float(best_sig.signal_score),
            "direction": best_sig.direction,
        }

    streak = 0
    streak_type = ""
    recent_outcomes_q = (
        select(SignalOutcome.direction_correct)
        .join(Signal, Signal.id == SignalOutcome.signal_id)
        .where(SignalOutcome.direction_correct.is_not(None))
        .order_by(desc(Signal.created_at))
        .limit(20)
    )
    recent_outcomes = (await db.execute(recent_outcomes_q)).scalars().all()
    if recent_outcomes:
        first_val = recent_outcomes[0]
        streak_type = "win" if first_val else "loss"
        for val in recent_outcomes:
            if val == first_val:
                streak += 1
            else:
                break

    return DashboardKpisResponse(
        total_signals=total,
        signals_today=signals_today,
        resolved_signals=resolved,
        win_rate=round(wins / resolved * 100, 1) if resolved > 0 else None,
        wins=wins,
        losses=losses,
        best_signal=best_data,
        avg_score=round(float(avg_score_val), 1) if avg_score_val else None,
        streak=streak,
        streak_type=streak_type,
    )


# ── Track Record (public leaderboard) ────────────────────────────────
@router.get("/analytics/track-record", response_model=TrackRecordResponse)
async def get_track_record(db: AsyncSession = Depends(get_db_session)):
    from datetime import datetime, timedelta, timezone

    total = (await db.execute(select(func.count()).select_from(Signal))).scalar() or 0

    resolved_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label.is_not(None))
    )
    resolved = (await db.execute(resolved_q)).scalar() or 0

    correct_q = (
        select(func.count())
        .select_from(SignalOutcome)
        .where(SignalOutcome.outcome_label == 1)
    )
    correct = (await db.execute(correct_q)).scalar() or 0
    overall_wr = round(correct / resolved * 100, 1) if resolved > 0 else None

    weekly_q = (
        select(
            func.date_trunc("week", Signal.created_at).label("week"),
            func.count(Signal.id).label("total"),
            func.sum(
                func.cast(SignalOutcome.outcome_label == 1, Integer)
            ).label("correct"),
            func.count(SignalOutcome.outcome_label).label("resolved"),
        )
        .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .group_by("week")
        .order_by(desc("week"))
        .limit(12)
    )
    weekly_rows = (await db.execute(weekly_q)).all()
    weekly = []
    for r in weekly_rows:
        w_total, w_correct, w_resolved = r[1], r[2] or 0, r[3] or 0
        weekly.append({
            "week": str(r[0].date()) if r[0] else None,
            "total_signals": w_total,
            "resolved": w_resolved,
            "correct": w_correct,
            "win_rate": round(w_correct / w_resolved * 100, 1) if w_resolved > 0 else None,
        })

    bucket_q = (
        select(
            Event.bucket,
            func.count(Signal.id).label("total"),
            func.sum(
                func.cast(SignalOutcome.outcome_label == 1, Integer)
            ).label("correct"),
            func.count(SignalOutcome.outcome_label).label("resolved"),
        )
        .join(Signal, Signal.event_id == Event.id)
        .outerjoin(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(Event.bucket.is_not(None))
        .group_by(Event.bucket)
    )
    bucket_rows = (await db.execute(bucket_q)).all()
    by_bucket = {}
    for r in bucket_rows:
        bkt = r[0] or "other"
        b_total, b_correct, b_resolved = r[1], r[2] or 0, r[3] or 0
        by_bucket[bkt] = {
            "total": b_total,
            "resolved": b_resolved,
            "correct": b_correct,
            "win_rate": round(b_correct / b_resolved * 100, 1) if b_resolved > 0 else None,
        }

    from sqlalchemy.orm import selectinload
    recent_q = (
        select(Signal)
        .options(selectinload(Signal.outcome), selectinload(Signal.event))
        .join(SignalOutcome, SignalOutcome.signal_id == Signal.id)
        .where(SignalOutcome.outcome_label.is_not(None))
        .order_by(desc(Signal.created_at))
        .limit(20)
    )
    recent_signals = (await db.execute(recent_q)).scalars().all()
    recent_resolved = []
    for s in recent_signals:
        o = s.outcome
        recent_resolved.append({
            "signal_id": s.id,
            "event_title": s.event.event_title if s.event else None,
            "direction": s.direction,
            "score": float(s.signal_score),
            "outcome_label": o.outcome_label if o else None,
            "direction_correct": o.direction_correct if o else None,
            "created_at": s.created_at.isoformat(),
        })

    return TrackRecordResponse(
        total_signals=total,
        resolved_signals=resolved,
        overall_win_rate=overall_wr,
        weekly=weekly,
        by_bucket=by_bucket,
        recent_resolved=recent_resolved,
    )
