"""Celery tasks — scoring pipeline (hybrid search → LLM → score → signal).

Key optimisation: LLM impact analyses run in PARALLEL via asyncio.gather,
cutting the dominant latency from 5×sequential to 1×parallel.
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone

from app.workers._async_helpers import run_async as _run_async
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _signal_dedupe_key(market_id: str, event_title: str, bucket: str | None) -> str:
    norm = f"{bucket or ''}|{market_id}|{(event_title or '').strip().lower()[:500]}"
    return hashlib.sha256(norm.encode()).hexdigest()[:48]


# ── Quality filters (Filter A: market state, Filter D: catalyst sanity) ──
#
# These filters reject obvious garbage signals BEFORE they reach the scorer.
# They were added after a Bloomberg-X-podcast-promo tweet generated a
# "Ternus appointed CEO of Apple" signal on a market trading at 32%
# (illiquid + hallucinated catalyst). See comments in each helper.

# ── Per-event source-quality derivation (audit 2026-04-25 P0-2 + P1.3) ──
#
# The SignalBuilder consumes `event_data["source_weight"]` and
# `event_data["source_tier"]` to score the cluster. Pre-fix, the call site
# hardcoded source_weight=0.8 and never passed source_tier (defaulting to
# tier 2 inside FeatureBuilder), throwing away the actual source quality
# we already had in News rows.
#
# Selection: max(weight) and min(tier) across the cluster — best-of-cluster,
# matching the heuristic intuition that one Reuters confirmation defines
# the cluster's authority even if other repostings are weaker. NULLs are
# skipped (vs. treated as 0/∞) so old rows missing the metadata don't
# poison the derivation.
# ── Pure dict builders for the scoring pipeline (audit follow-up) ──
#
# The previous inline construction used `if x else None`, which silently
# coerced legitimate zero values (last_trade_price=0 on deeply-NO markets,
# spread=0 on tight markets, ambiguity=0) to None. That bypassed downstream
# filters and band checks. These helpers preserve real zeros and only emit
# None for actually-missing data.
def _build_market_data(market) -> dict:
    """Build the market_data dict consumed by SignalBuilder.

    Preserves zero values (a deeply-NO market with last_trade_price=0 is
    real data, not missing data). Audit 2026-04-25 follow-up [P0].
    """
    return {
        "liquidity": (
            float(market.liquidity) if market.liquidity is not None else None
        ),
        "spread": (
            float(market.spread) if market.spread is not None else None
        ),
        "end_date": market.end_date,
        "last_trade_price": (
            float(market.last_trade_price)
            if market.last_trade_price is not None
            else None
        ),
    }


def _build_llm_data(analysis) -> dict | None:
    """Build the llm_data dict consumed by SignalBuilder, or None if no
    analysis row exists. Preserves zero scores. Audit 2026-04-25 follow-up.
    """
    if analysis is None:
        return None
    return {
        "impact_direction": analysis.impact_direction,
        "impact_strength": (
            float(analysis.impact_strength)
            if analysis.impact_strength is not None
            else None
        ),
        "llm_confidence": (
            float(analysis.llm_confidence)
            if analysis.llm_confidence is not None
            else None
        ),
        "ambiguity_score": (
            float(analysis.ambiguity_score)
            if analysis.ambiguity_score is not None
            else None
        ),
        "specificity_score": (
            float(analysis.specificity_score)
            if analysis.specificity_score is not None
            else None
        ),
    }


def _derive_event_source_signals(
    rows: list[tuple[str | None, int | None, float | None]],
) -> dict:
    """Pure helper — derive per-event source_weight + source_tier from a
    list of (source_name, source_tier, source_weight) cluster rows.

    Returns a dict with keys 'source_weight' (float) and 'source_tier' (int).
    Defaults match SignalBuilder/FeatureBuilder behaviour: 0.5 / 2.
    """
    weights = [w for _n, _t, w in rows if w is not None]
    tiers = [t for _n, t, _w in rows if t is not None]
    return {
        "source_weight": max(weights) if weights else 0.5,
        "source_tier": min(tiers) if tiers else 2,
    }


# Filter A thresholds — markets too thin/resolved to trade meaningfully
MIN_VOLUME_24H_USD = 500.0       # below this, market is dead inventory
MIN_LIQUIDITY_USD = 2_000.0      # below this, slippage destroys edge
RESOLVED_PRICE_HIGH = 0.97       # market priced "almost certainly YES"
RESOLVED_PRICE_LOW = 0.03        # market priced "almost certainly NO"


def _market_quality_reject(market) -> str | None:
    """Return rejection reason if the market is too low-quality to signal on.

    Three sub-filters, all on Polymarket-side state (not signal-side):
    1) volume_24h < $500 → market is illiquid spam, no one trades it
    2) liquidity < $2k   → spread will eat the edge before you can fill
    3) price > 0.97 or < 0.03 → market has effectively resolved, no edge left
    """
    vol_24h = float(market.volume_24h) if market.volume_24h is not None else 0.0
    if vol_24h < MIN_VOLUME_24H_USD:
        return f"volume_24h ${vol_24h:.0f} < ${MIN_VOLUME_24H_USD:.0f}"

    liq = float(market.liquidity) if market.liquidity is not None else 0.0
    if liq < MIN_LIQUIDITY_USD:
        return f"liquidity ${liq:.0f} < ${MIN_LIQUIDITY_USD:.0f}"

    price = float(market.last_trade_price) if market.last_trade_price is not None else None
    if price is not None and (price >= RESOLVED_PRICE_HIGH or price <= RESOLVED_PRICE_LOW):
        return f"price {price:.3f} outside ({RESOLVED_PRICE_LOW},{RESOLVED_PRICE_HIGH})"

    return None


# Filter D — catalyst certainty regex.
# Detects past-tense factual assertions in the event_summary like "X has been
# appointed", "Y has resigned", "Z was selected". These should match REALITY
# (i.e., the underlying market should already be > 0.5 if true). When the
# catalyst confidently asserts a YES outcome but the market is at 32%, the
# catalyst is almost always hallucinated/spam (case in point: a podcast title
# "how Ternus became Apple's next CEO" → catalyst "Ternus has been appointed").
#
# Applied ONLY to BUY_YES with market < 0.5 because the BUY_NO branch
# catches too many legitimate contrarian plays (e.g., "Iran refused →
# BUY_NO 'Will meeting be in Pakistan'" at market 88% IS valid alpha).
_CATALYST_CERTAINTY_RE = re.compile(
    r"(?i)("
    r"(?:has been|have been|was|were)\s+"
    r"(?:appointed|named|elected|chosen|selected|signed|approved|confirmed|"
    r"nominated|sworn|inaugurated|promoted|fired|resigned|killed|arrested|"
    r"indicted|convicted|defeated|launched|released|ratified|passed|rejected|"
    r"vetoed|granted|denied|downgraded|upgraded|seized|engaged)"
    r"|"
    r"(?:has|have)\s+"
    r"(?:ordered|signed|won|lost|died|resigned|fired|killed|launched|approved|"
    r"rejected|confirmed|announced|admitted|conceded|declared)"
    r")"
)
CATALYST_MARKET_DISAGREE_THRESHOLD = 0.5


def _catalyst_disagrees_with_market(
    event_summary: str | None,
    direction: str,
    last_trade_price: float | None,
) -> str | None:
    """Return rejection reason if catalyst confidently asserts YES but market
    disagrees (BUY_YES < 0.5). Returns None otherwise.

    Only the BUY_YES side is checked — see module docstring above.
    """
    if direction != "BUY_YES":
        return None
    if last_trade_price is None or last_trade_price >= CATALYST_MARKET_DISAGREE_THRESHOLD:
        return None
    if not event_summary:
        return None
    m = _CATALYST_CERTAINTY_RE.search(event_summary)
    if m is None:
        return None
    return f"catalyst asserts '{m.group(0)}' but BUY_YES market at {last_trade_price:.2f}"


# Filter B — score penalty for low source diversity (NOT a hard reject).
# 95% of events have a single distinct source_name (small clusters from the
# event-linking pipeline). Hard-rejecting would nuke nearly all signals;
# instead we apply a multiplicative penalty so multi-source events get
# priority without killing inventory.
LOW_DIVERSITY_PENALTY = 0.85   # 15% score penalty
LOW_DIVERSITY_THRESHOLD = 2    # need >= 2 distinct source_name to avoid penalty


# ══════════════════════════════════════════════════════════════════════════
# Measurement-layer helpers — fetch data the baselines need at signal time.
# Kept module-level (not nested) so the integration tests can patch them.
# ══════════════════════════════════════════════════════════════════════════

async def _fetch_baseline_articles(session, *, event_id: int) -> list[dict]:
    """Return [{source_weight: float}, ...] for the news_sentiment baseline.

    Joins event_news_links → news_clean → news to recover the per-article
    source_weight that was lost when we collapsed to (clean_id, excerpt) for
    the audit row. Capped at 20 articles — the sigmoid in the baseline
    saturates well before then and we don't want to spend N×SELECT on tail
    sources for an O(1) prediction.

    Failure-tolerant: any exception → empty list (news_sentiment baseline
    silently returns None and no row is written for that variant).
    """
    from sqlalchemy import select

    from app.db.models import EventNewsLink, News, NewsClean

    try:
        rows = (
            await session.execute(
                select(News.source_weight)
                .join(NewsClean, NewsClean.news_id == News.id)
                .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
                .where(EventNewsLink.event_id == event_id)
                .order_by(EventNewsLink.relevance_score.desc().nullslast())
                .limit(20)
            )
        ).all()
    except Exception:
        logger.exception(
            "tasks_scoring._fetch_baseline_articles: event_id=%s failed",
            event_id,
        )
        return []

    return [
        {"source_weight": float(r[0])}
        for r in rows
        if r[0] is not None
    ]


async def _fetch_market_price_24h_ago(market) -> float | None:
    """Pull the YES probability ~24h ago from Polymarket's /prices-history.

    Returns None when:
      • `market` or its `clob_token_ids` are missing (legacy rows)
      • the YES token id can't be resolved
      • the API call fails / 404s / returns no history (brand-new markets)

    The momentum_24h baseline treats None as 'skip this prediction' so a
    transient Polymarket outage simply means one fewer baseline row, not a
    failed signal commit.
    """
    if market is None:
        return None
    token_ids = getattr(market, "clob_token_ids", None) or {}
    yes_token_id = token_ids.get("yes") if isinstance(token_ids, dict) else None
    if not yes_token_id:
        return None

    from app.polymarket.clob_client import ClobClient

    client = ClobClient()
    try:
        return await client.get_price_24h_ago(str(yes_token_id))
    except Exception:
        logger.exception(
            "tasks_scoring._fetch_market_price_24h_ago: token=%s failed",
            yes_token_id,
        )
        return None
    finally:
        await client.close()


# ══════════════════════════════════════════════════════════════════════════
# Phase 5 — Hybrid search → LLM impact → score → signal (all in one task)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=10)
def run_hybrid_search(self, event_id: int):
    """Find candidates, run parallel LLM analysis, generate signals — one task."""
    try:
        return _run_async(_run_full_scoring_pipeline(event_id))
    except Exception as exc:
        logger.exception("run_hybrid_search failed for event_id=%s", event_id)
        raise self.retry(exc=exc, throw=False) from exc


async def _run_full_scoring_pipeline(event_id: int) -> dict:
    """Combined hybrid-search + parallel-LLM + score pipeline in one async call."""
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    # Importing app.measurement registers the four built-in baselines into
    # the global VariantRegistry singleton — required before
    # record_baselines_for_signal is invoked below.
    import app.measurement  # noqa: F401
    from app.db.models import (
        Event,
        EventMarketAnalysis,
        EventMarketCandidate,
        EventNewsLink,
        Market,
        Signal,
    )
    from app.llm.impact_analyzer import create_impact_analyzer
    from app.measurement.pipeline import record_baselines_for_signal
    from app.processing.embedding_service import get_embedding
    from app.processing.freshness import signal_event_still_fresh
    from app.retrieval import hybrid_search_markets  # dispatcher (v1 by default)
    from app.signal.signal_builder import create_signal_builder
    from app.sourcing.prod_trace import record_prod_signal_articles

    settings = get_settings()
    max_llm = settings.llm_impact_max_candidates

    async with async_session_factory() as session:
        event = (
            await session.execute(select(Event).where(Event.id == event_id))
        ).scalar_one_or_none()

        if not event:
            return {"status": "event_not_found", "event_id": event_id}

        if not signal_event_still_fresh(
            event.last_seen,
            max_age_hours=settings.signal_event_max_age_hours,
        ):
            event.processing_status = "skipped_stale"
            await session.commit()
            return {"status": "event_too_stale", "event_id": event_id}

        skip_llm = event.processing_status in ("llm_done", "scoring_done")

        # ── Step 1: Event embedding ──────────────────────────────────
        raw_embedding = event.embedding
        if raw_embedding is None:
            text_for_embed = event.event_retrieval_text or event.event_title
            raw_embedding = await get_embedding(text_for_embed)
            if raw_embedding is not None:
                event.embedding = raw_embedding
                await session.flush()

        # v2 event embedding — best-effort; failure does not block scoring
        if event.embedding_v2 is None:
            from app.processing.text_composers import compose_event_v2
            composed_v2 = compose_event_v2(
                event.event_title, event.event_summary or "",
                list(event.key_entities or []), bucket=event.bucket,
            )
            try:
                v2_emb = await get_embedding(composed_v2.text)
            except Exception as exc:
                logger.warning("event embedding_v2 failed event_id=%s: %s", event_id, exc)
                v2_emb = None
            if v2_emb is not None:
                # datetime/timezone come from module-level import at top of file
                event.embedding_v2 = v2_emb
                event.embedding_v2_composition = composed_v2.composition_version
                event.embedding_v2_computed_at = datetime.now(timezone.utc)
                await session.flush()

        if raw_embedding is None:
            event.processing_status = "failed_no_embedding"
            await session.commit()
            return {"status": "no_embedding", "event_id": event_id}

        embedding = list(raw_embedding)
        event_text = event.event_retrieval_text or event.event_title

        # ── Step 2: Hybrid search ────────────────────────────────────
        candidates = await hybrid_search_markets(
            session, embedding, event_text,
            event_bucket=event.bucket,
            event_entities=event.key_entities,
            event_last_seen=event.last_seen,
        )

        if not candidates:
            event.processing_status = "no_candidates"
            await session.commit()
            return {"status": "no_candidates", "event_id": event_id}

        for c in candidates:
            existing = (
                await session.execute(
                    select(EventMarketCandidate).where(
                        EventMarketCandidate.event_id == event_id,
                        EventMarketCandidate.market_id == c["market_id"],
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.bm25_score = c.get("bm25_score")
                existing.cosine_score = c.get("cosine_score")
                existing.rrf_score = c.get("rrf_score")
                existing.rank = c.get("rank")
            else:
                session.add(EventMarketCandidate(
                    event_id=event_id,
                    market_id=c["market_id"],
                    bm25_score=c.get("bm25_score"),
                    cosine_score=c.get("cosine_score"),
                    rrf_score=c.get("rrf_score"),
                    rank=c.get("rank"),
                ))

        event.processing_status = "candidates_found"
        await session.flush()

        # ── chantier #4: fire-and-forget shadow ranking ──────────────────
        if settings.ranking_shadow_enabled:
            try:
                from app.workers.tasks_ranking_shadow import record_shadow_ranking
                record_shadow_ranking.delay(event_id=event_id)
            except Exception:
                logger.warning(
                    "ranking shadow enqueue failed event_id=%s — continuing",
                    event_id,
                    exc_info=True,
                )

        # ── Step 3: Parallel LLM impact analysis ─────────────────────
        top_cands = candidates[:max_llm]
        analyzed = 0
        llm_results: list = []

        if not skip_llm:
            event_full_text = f"{event.event_title}. {event.event_summary or ''}"
            analyzer = create_impact_analyzer()

            async def _analyze_one(cand_dict: dict) -> dict | None:
                mid = cand_dict["market_id"]
                market = (
                    await session.execute(
                        select(Market).where(Market.market_id == mid)
                    )
                ).scalar_one_or_none()
                if not market:
                    return None

                already = (
                    await session.execute(
                        select(EventMarketAnalysis)
                        .where(
                            EventMarketAnalysis.event_id == event_id,
                            EventMarketAnalysis.market_id == mid,
                        )
                        .order_by(EventMarketAnalysis.id.desc())
                        .limit(1)
                    )
                ).scalar_one_or_none()
                if already:
                    return {"market_id": mid, "skipped": True}

                result = await analyzer.analyze(event_full_text, market.question)
                if not result:
                    return None

                session.add(EventMarketAnalysis(
                    event_id=event_id,
                    market_id=mid,
                    impact_direction=result.get("impact_direction") or result.get("direction"),
                    impact_strength=_safe_float(result.get("impact_strength") or result.get("impact_score")),
                    llm_confidence=_safe_float(result.get("llm_confidence") or result.get("confidence")),
                    ambiguity_score=_safe_float(result.get("ambiguity_score")),
                    specificity_score=_safe_float(result.get("specificity_score")),
                    catalysts=result.get("catalysts"),
                    risks=result.get("risks"),
                    reasoning=result.get("reasoning"),
                ))
                return {"market_id": mid, "analysis": result}

            llm_results = await asyncio.gather(
                *[_analyze_one(c) for c in top_cands],
                return_exceptions=True,
            )

            for r in llm_results:
                if isinstance(r, dict) and not r.get("skipped"):
                    analyzed += 1
                elif isinstance(r, Exception):
                    logger.warning("LLM analysis failed: %s", r)

            event.processing_status = "llm_done"
            await session.flush()

        # ── Step 4: Score candidates, keep only the best signal per event ─
        builder = create_signal_builder()
        signals_created = 0
        best_signal = None
        best_signal_mid = None
        best_market = None  # captured alongside best_signal for clob_token_ids lookup
        best_score = -1

        scored_mids = set()
        for r in llm_results:
            if not isinstance(r, dict) or "market_id" not in r:
                continue
            scored_mids.add(r["market_id"])

        all_analyses = (
            await session.execute(
                select(EventMarketAnalysis)
                .where(EventMarketAnalysis.event_id == event_id)
            )
        ).scalars().all()
        for a in all_analyses:
            scored_mids.add(a.market_id)

        cosine_by_mid = {}
        for c in candidates:
            cosine_by_mid[c["market_id"]] = c.get("cosine_score")

        # ── Pre-fetch event-level source data once (avoids N+1) ──────
        # Used by:
        #  • Filter B (penalty for single-source events)
        #  • Filter E (source_tier_mix as shares, persisted on the Signal)
        from app.db.models import News, NewsClean
        src_rows = (
            await session.execute(
                select(News.source_name, News.source_tier, News.source_weight)
                .join(NewsClean, NewsClean.news_id == News.id)
                .join(EventNewsLink, EventNewsLink.clean_id == NewsClean.id)
                .where(EventNewsLink.event_id == event_id)
            )
        ).all()
        distinct_source_names = {r[0] for r in src_rows if r[0]}
        # Per-event source authority (best-of-cluster) — feeds the SignalBuilder.
        # Audit 2026-04-25 P0-2 + P1.3.
        event_src_signals = _derive_event_source_signals(
            [(r[0], r[1], r[2]) for r in src_rows]
        )
        tier_counts: dict[str, int] = {}
        for _name, tier, _weight in src_rows:
            if tier is None:
                continue
            key = f"tier_{int(tier)}"
            tier_counts[key] = tier_counts.get(key, 0) + 1
        total_articles = sum(tier_counts.values()) or 0
        source_tier_mix = (
            {k: round(v / total_articles, 4) for k, v in tier_counts.items()}
            if total_articles
            else None
        )

        for mid in scored_mids:
            market = (
                await session.execute(
                    select(Market).where(Market.market_id == mid)
                )
            ).scalar_one_or_none()
            if not market:
                continue

            # ── Persist EventMarketFeatures BEFORE any rejection gate ──
            # Audit 2026-04-25 follow-up: the offline gate-effectiveness
            # backtest needs at-time features for every analyzed pair —
            # including those rejected by Filter A / cooloff / etc. We
            # snapshot here and let the gates filter downstream signal
            # creation as before.
            analysis = (
                await session.execute(
                    select(EventMarketAnalysis)
                    .where(
                        EventMarketAnalysis.event_id == event_id,
                        EventMarketAnalysis.market_id == mid,
                    )
                    .order_by(EventMarketAnalysis.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

            event_data = {
                "first_seen": event.first_seen,
                "last_seen": event.last_seen,
                "unique_sources_count": event.unique_sources_count,
                # Real per-event source authority — best-of-cluster.
                # Audit 2026-04-25 P0-2 + P1.3.
                "source_weight": event_src_signals["source_weight"],
                "source_tier": event_src_signals["source_tier"],
            }
            # Audit 2026-04-25 follow-up [P0]: use is-not-None helpers so
            # legitimate zeros (deeply-NO price, zero spread, ambiguity=0)
            # reach the SignalBuilder instead of being coerced to None.
            market_data = _build_market_data(market)
            llm_data = _build_llm_data(analysis)

            try:
                from app.scoring.event_market_features_writer import (
                    upsert_event_market_features,
                )
                from app.scoring.feature_dict import build_feature_dict

                ref_dt = (
                    event.last_seen
                    or event.first_seen
                    or datetime.now(timezone.utc)
                )
                source_count = event.unique_sources_count or 1
                features_dict = build_feature_dict(
                    event_data=event_data,
                    market_data=market_data,
                    ref_dt=ref_dt,
                    source_count=source_count,
                )
                await upsert_event_market_features(
                    session,
                    event_id=event_id,
                    market_id=mid,
                    features=features_dict,
                    impact_strength=(
                        float(analysis.impact_strength)
                        if analysis is not None and analysis.impact_strength is not None
                        else None
                    ),
                    llm_confidence=(
                        float(analysis.llm_confidence)
                        if analysis is not None and analysis.llm_confidence is not None
                        else None
                    ),
                    ambiguity_score=(
                        float(analysis.ambiguity_score)
                        if analysis is not None and analysis.ambiguity_score is not None
                        else None
                    ),
                )
            except Exception:
                # Persistence is observability — never block scoring on a
                # features write failure.
                logger.exception(
                    "event_market_features upsert failed event=%s market=%s",
                    event_id, mid,
                )

            # Filter A — market quality (volume / liquidity / resolved).
            # Pre-build_signal because there's no point scoring a $57/24h
            # market with $9k liquidity (the Ternus case).
            reject_reason = _market_quality_reject(market)
            if reject_reason:
                logger.info(
                    "Market quality reject mid=%s: %s",
                    mid, reject_reason,
                )
                continue

            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                break

            existing_signal = (
                await session.execute(
                    select(Signal)
                    .where(
                        Signal.event_id == event_id,
                        Signal.market_id == mid,
                    )
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing_signal:
                continue

            market_cooloff = datetime.now(timezone.utc) - timedelta(hours=6)
            recent_market_signal = (
                await session.execute(
                    select(Signal.id)
                    .where(
                        Signal.market_id == mid,
                        Signal.created_at >= market_cooloff,
                    )
                    .order_by(Signal.created_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            if recent_market_signal:
                logger.info("Market cooloff: market %s already has signal in last 6h", mid)
                continue

            mid_cosine = cosine_by_mid.get(mid)
            signal = builder.build_signal(
                event_id, mid, event_data, market_data, llm_data,
                cosine_score=mid_cosine,
            )
            if signal is None:
                continue

            # Filter D — catalyst-vs-market sanity for BUY_YES.
            # If event_summary asserts a definitive YES outcome but the
            # market is at < 0.5, the catalyst is likely a hallucinated
            # claim (e.g., podcast titles like "how Ternus became CEO"
            # extracted as fact). Run AFTER build_signal so we know the
            # final direction the scorer settled on.
            d_reject = _catalyst_disagrees_with_market(
                event.event_summary,
                signal.direction,
                float(market.last_trade_price) if market.last_trade_price is not None else None,
            )
            if d_reject:
                logger.info(
                    "Catalyst sanity reject mid=%s event=%s: %s",
                    mid, event_id, d_reject,
                )
                continue

            # Filter B — penalty (NOT reject) for single-source events.
            # Single-source signals still ship but at -15% score, so
            # multi-source events naturally float to the top of /signals.
            if len(distinct_source_names) < LOW_DIVERSITY_THRESHOLD:
                old_score = float(signal.signal_score)
                signal.signal_score = round(old_score * LOW_DIVERSITY_PENALTY, 1)
                logger.info(
                    "Diversity penalty mid=%s event=%s: %.1f → %.1f (%d distinct sources)",
                    mid, event_id, old_score, signal.signal_score,
                    len(distinct_source_names),
                )

            # Filter E — populate source_tier_mix (as shares, e.g.
            # {"tier_1": 0.6, "tier_2": 0.4}). Read by signal_mapper
            # to compress the opportunity window for high-tier signals.
            if source_tier_mix is not None:
                signal.source_tier_mix = source_tier_mix

            signal.score_label = getattr(signal, "_score_label", None)
            signal.score_explanation = getattr(signal, "_score_explanation", None)
            signal.window_estimate = getattr(signal, "_window_estimate", None)
            signal.yes_probability_explanation = getattr(signal, "_yes_probability_explanation", None)
            is_below = getattr(signal, "_below_threshold", False)

            if is_below:
                dedupe_key = _signal_dedupe_key(mid, event.event_title, event.bucket)
                signal.dedupe_key = dedupe_key
                session.add(signal)
                await session.flush()
                logger.info(
                    "Sub-threshold signal logged: id=%d event=%d market=%s score=%.1f",
                    signal.id, event_id, mid, signal.signal_score,
                )
                continue

            if signal.signal_score > best_score:
                best_score = signal.signal_score
                best_signal = signal
                best_signal_mid = mid
                best_market = market

        if best_signal is not None:
            dedupe_key = _signal_dedupe_key(best_signal_mid, event.event_title, event.bucket)
            best_signal.dedupe_key = dedupe_key
            session.add(best_signal)
            await session.flush()

            # Persist the prod signal_articles audit row so the SignalCard
            # `0 sources` bug is fixed and shadow variants have a baseline
            # to join against. The articles are sourced from event_news_links
            # ordered by relevance (NULLS last, since older rows lack scores).
            try:
                links_result = await session.execute(
                    select(EventNewsLink.clean_id, EventNewsLink.key_excerpt)
                    .where(EventNewsLink.event_id == event_id)
                    .order_by(EventNewsLink.relevance_score.desc().nullslast())
                    .limit(10)
                )
                article_rows = [
                    {"news_clean_id": cid, "excerpt": exc}
                    for cid, exc in links_result.all()
                ]
                if article_rows:
                    await record_prod_signal_articles(
                        session, signal_id=best_signal.id, articles=article_rows,
                    )
            except Exception:
                logger.exception(
                    "tasks_scoring: record_prod_signal_articles failed signal_id=%s",
                    best_signal.id,
                )

            # Measurement layer — write heuristic_v1 + 4 baseline rows into
            # signal_predictions so chantier #1 metrics (Brier, Wilson CI,
            # simulated_pnl) actually have data to chew on for live prod
            # signals. Without this call, the prod path produces zero
            # evaluable predictions and the 10-day clean-collect window
            # yields no usable benchmark data. The helper internally
            # swallows failures so a broken baseline cannot abort the
            # signal commit. The sync builder stashed `_features` and
            # `_llm_combined` on the Signal so the optional
            # 'heuristic_shadow' row can be written when the flag is on.
            #
            # We feed two pieces of richer context here:
            #   • `articles` with real `source_weight` from the News table
            #     so the news_sentiment baseline has weights to aggregate.
            #     `direction` is left implicit (NEUTRAL) until per-article
            #     directional sentiment is added in a future chantier — the
            #     baseline currently degenerates to a constant 0.5 / BUY_NO
            #     prediction. Wiring the path now means the moment we add
            #     direction labels upstream, the baseline activates without
            #     touching this file.
            #   • `market_price_24h_ago` fetched from Polymarket
            #     /prices-history so the momentum_24h baseline produces a
            #     real, non-degenerate prediction. Failures (network, 404,
            #     missing token id, brand-new market) silently fall back to
            #     None — the baseline returns None and the row is skipped.
            articles_for_baselines = await _fetch_baseline_articles(
                session, event_id=event_id
            )
            price_24h_ago = await _fetch_market_price_24h_ago(best_market)
            await record_baselines_for_signal(
                session,
                signal=best_signal,
                articles=articles_for_baselines,
                market_price_24h_ago=price_24h_ago,
            )

            _schedule_price_captures(best_signal.id, best_signal_mid)
            # Audit follow-up [P1]: Signal.created_at uses
            # server_default=func.now(); the Python attribute stays None
            # after flush() until refresh() (session has
            # expire_on_commit=False so commit alone doesn't reload).
            # Without this refresh, every WS subscriber gets created_at=null.
            await session.refresh(best_signal, ["created_at"])
            await _broadcast_signal(best_signal)
            signals_created = 1

            logger.info(
                "Signal created: id=%d event=%d market=%s score=%.1f dir=%s",
                best_signal.id, event_id, best_signal_mid,
                best_signal.signal_score, best_signal.direction,
            )

        event.processing_status = "scoring_done"
        await session.commit()

    logger.info(
        "Scoring pipeline: event=%d → %d candidates, %d LLM analyses, %d signals",
        event_id, len(candidates), analyzed, signals_created,
    )
    return {
        "status": "ok",
        "event_id": event_id,
        "candidates": len(candidates),
        "analyzed": analyzed,
        "signals_created": signals_created,
    }


# ══════════════════════════════════════════════════════════════════════════
# Legacy entry points (kept for backward-compatible beat schedule dispatch)
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def run_llm_impact(self, event_id: int):
    """Redirects to full scoring pipeline."""
    try:
        return _run_async(_run_full_scoring_pipeline(event_id))
    except Exception as exc:
        logger.exception("run_llm_impact failed for event_id=%s", event_id)
        raise self.retry(exc=exc, throw=False) from exc


@celery_app.task(bind=True, max_retries=1)
def compute_score_and_signal(self, event_id: int, market_id: str):
    """Legacy — full pipeline already handles scoring inline."""
    return {"status": "handled_by_full_pipeline", "event_id": event_id, "market_id": market_id}


# ══════════════════════════════════════════════════════════════════════════
# Retry stuck events
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def retry_stuck_events(self):
    try:
        return _run_async(_retry_stuck_events_async())
    except Exception as exc:
        logger.exception("retry_stuck_events failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _retry_stuck_events_async() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Event
    from app.processing.freshness import signal_event_still_fresh

    settings = get_settings()

    retryable = ["candidates_found", "new", "no_candidates", "llm_done"]

    async with async_session_factory() as session:
        stuck = (
            await session.execute(
                select(Event)
                .where(Event.processing_status.in_(retryable))
                .order_by(Event.last_seen.desc())
                .limit(30)
            )
        ).scalars().all()

        if not stuck:
            return {"status": "nothing_stuck"}

        dispatched = 0
        skipped_stale = 0
        for event in stuck:
            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                event.processing_status = "skipped_stale"
                skipped_stale += 1
                continue
            run_hybrid_search.apply_async(args=[event.id], queue="scoring")
            dispatched += 1

        await session.commit()

    logger.info("retry_stuck_events: dispatched=%d skipped_stale=%d", dispatched, skipped_stale)
    return {"status": "ok", "dispatched": dispatched, "skipped_stale": skipped_stale}


# ══════════════════════════════════════════════════════════════════════════
# Re-score events that completed scoring but produced 0 signals
# ══════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, max_retries=1)
def rescore_zero_signal_events(self):
    try:
        return _run_async(_rescore_zero_signal_events_async())
    except Exception as exc:
        logger.exception("rescore_zero_signal_events failed")
        raise self.retry(exc=exc, throw=False) from exc


async def _rescore_zero_signal_events_async() -> dict:
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.db.database import get_session_factory
    async_session_factory = get_session_factory()
    from app.db.models import Event, Signal
    from app.processing.freshness import signal_event_still_fresh

    settings = get_settings()

    async with async_session_factory() as session:
        signal_event_ids = select(Signal.event_id).distinct().scalar_subquery()

        zero_signal_events = (
            await session.execute(
                select(Event)
                .where(
                    Event.processing_status == "scoring_done",
                    Event.id.not_in(signal_event_ids),
                )
                .order_by(Event.last_seen.desc())
                .limit(20)
            )
        ).scalars().all()

        if not zero_signal_events:
            return {"status": "nothing_to_rescore"}

        dispatched = 0
        skipped_stale = 0
        for event in zero_signal_events:
            if not signal_event_still_fresh(
                event.last_seen,
                max_age_hours=settings.signal_event_max_age_hours,
            ):
                skipped_stale += 1
                continue
            event.processing_status = "candidates_found"
            run_hybrid_search.apply_async(args=[event.id], queue="scoring")
            dispatched += 1

        await session.commit()

    logger.info("rescore_zero_signal: dispatched=%d skipped_stale=%d", dispatched, skipped_stale)
    return {"status": "ok", "dispatched": dispatched, "skipped_stale": skipped_stale}


# ══════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════

def _schedule_price_captures(signal_id: int, market_id: str):
    from app.workers.tasks_outcomes import capture_price

    delays = [
        ("price_t5min", 5 * 60),
        ("price_t15min", 15 * 60),
        ("price_t1h", 60 * 60),
        ("price_t24h", 24 * 60 * 60),
    ]
    for field, countdown in delays:
        capture_price.apply_async(
            args=[signal_id, market_id, field],
            countdown=countdown,
            queue="default",
        )


async def _broadcast_signal(signal):
    """Push signal to Redis pub/sub (for WebSocket clients) + Telegram + push.

    Async so the network round-trips don't block the worker's persistent
    event loop (P0-5 audit fix, 2026-04-27).
    """
    import json

    payload = {
        "id": signal.id,
        "event_id": signal.event_id,
        "market_id": signal.market_id,
        "signal_score": float(signal.signal_score),
        "signal_strength": float(signal.signal_strength) if signal.signal_strength is not None else None,
        "trade_quality": float(signal.trade_quality) if signal.trade_quality is not None else None,
        "direction": signal.direction,
        "confidence_label": signal.confidence_label,
        "urgency_label": signal.urgency_label,
        "tradability_label": signal.tradability_label,
        # Audit follow-up [P1]: use is-not-None so a deeply-NO signal at
        # market_price_at_signal=0 isn't broadcast as null.
        "market_price_at_signal": (
            float(signal.market_price_at_signal)
            if signal.market_price_at_signal is not None
            else None
        ),
        "created_at": signal.created_at.isoformat() if signal.created_at else None,
    }

    # Audit P0-5 (2026-04-27): Redis publish + Telegram + push were
    # synchronous calls inside this async coroutine, blocking the
    # worker's persistent event loop for the duration of each network
    # round-trip (DNS+TLS handshakes, in particular for cold-start
    # Telegram). On a slow upstream a single high-conviction signal
    # could stall the scoring loop for seconds. All three side-effects
    # now run async or are offloaded to a thread so the loop stays
    # responsive.
    try:
        from redis.asyncio import from_url as _async_redis_from_url

        from app.core.config import get_settings
        _settings = get_settings()
        r = _async_redis_from_url(_settings.redis_url)
        try:
            await r.publish("signal:new", json.dumps(payload))
        finally:
            await r.aclose()
        logger.info("Broadcast signal id=%d to Redis pub/sub", signal.id)
    except Exception:
        logger.warning("Redis broadcast failed for signal id=%d", signal.id, exc_info=True)

    await _send_telegram_alert(signal)
    await _send_push_notification(signal)


async def _send_telegram_alert(signal):
    """Send a Telegram message for high-conviction signals.

    Uses `httpx.AsyncClient` so it doesn't block the worker's event
    loop even when Telegram's API is slow.
    """
    from app.core.config import get_settings

    settings = get_settings()
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    if not token or not chat_id:
        return

    score = float(signal.signal_score)
    if score < settings.signal_score_threshold:
        return

    direction = signal.direction or "NEUTRAL"
    price_str = f"{float(signal.market_price_at_signal) * 100:.1f}%" if signal.market_price_at_signal else "--"
    conf = (signal.confidence_label or "").upper()
    urgency = (signal.urgency_label or "").upper()

    if score >= 90:
        tier = "EXCEPTIONAL"
    elif score >= 75:
        tier = "HIGH CONVICTION"
    elif score >= 60:
        tier = "ACTIONABLE"
    else:
        tier = "MONITORING"

    text = (
        f"{'🟢' if 'YES' in direction else '🔴'} *Signal #{signal.id}* — {tier}\n\n"
        f"*Score:* {score:.0f}/100\n"
        f"*Direction:* {direction}\n"
        f"*Market price:* {price_str} YES\n"
        f"*Confidence:* {conf}\n"
        f"*Urgency:* {urgency}\n\n"
        f"[Open in Signal](https://signal.app/opportunity/{signal.id})"
    )

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            )
        if resp.status_code == 200:
            logger.info("Telegram alert sent for signal id=%d", signal.id)
        else:
            logger.warning("Telegram API returned %d: %s", resp.status_code, resp.text[:200])
    except Exception:
        logger.warning("Telegram alert failed for signal id=%d", signal.id, exc_info=True)


async def _send_push_notification(signal):
    """Send PWA push notification for high-conviction signals.

    `send_push_to_all` is sync (uses sync `redis.smembers` + `pywebpush`).
    Offload via `asyncio.to_thread` so the I/O fan-out runs on a worker
    thread rather than blocking the scoring event loop.
    """
    import asyncio

    score = float(signal.signal_score)
    if score < 60:
        return
    try:
        from app.api.push import send_push_to_all
        direction = signal.direction or "NEUTRAL"
        await asyncio.to_thread(
            send_push_to_all,
            title=f"Signal #{signal.id} — {score:.0f}/100",
            body=f"{direction} | Market price {float(signal.market_price_at_signal) * 100:.0f}% YES" if signal.market_price_at_signal else f"{direction}",
            url=f"/opportunity/{signal.id}",
            tag=f"signal-{signal.id}",
        )
    except Exception:
        logger.debug("Push notification failed for signal %d", signal.id, exc_info=True)


def _safe_float(val, scale: int = 1) -> float | None:
    if val is None:
        return None
    try:
        return float(val) / scale
    except (ValueError, TypeError):
        return None


def _is_quota_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "insufficient_quota" in msg
        or "quota" in msg
        or "429" in msg
        or "rate limit" in msg
    )


# NOTE 2026-04-25 (updated 2026-04-27): `_score_event_market_async` was
# removed; it was the only writer to `SignalPendingReasoning`. The live
# scoring path uses the sync `SignalBuilder` via `_run_full_scoring_pipeline`.
# The 10-min beat schedule was removed in 2026-04-27 (P1-4) since the
# table has had zero producers for months. The task below remains as an
# ad-hoc manual rescue (`celery -A app.workers.celery_app call
# app.workers.tasks_scoring.backfill_reasoning`) in case stragglers from
# pre-2026-04-25 deploys ever resurface. A future chantier can drop the
# `SignalPendingReasoning` table + this task entirely.


async def _backfill_reasoning_async(limit: int = 50, *, analyzer=None) -> int:
    from sqlalchemy import delete, select

    from app.db.database import get_session_factory
    from app.db.models import SignalPendingReasoning
    from app.llm.reasoning_analyzer import create_reasoning_analyzer
    from app.signal.signal_builder import build_signal

    analyzer = analyzer or create_reasoning_analyzer()

    session_factory = get_session_factory()
    done = 0
    async with session_factory() as s:
        rows = (await s.execute(
            select(SignalPendingReasoning).order_by(SignalPendingReasoning.created_at).limit(limit)
        )).scalars().all()

    for row in rows:
        inputs = row.inputs or {}
        try:
            result = await build_signal(
                event=inputs["event"],
                market=inputs["market"],
                articles=inputs["articles"],
                analyzer=analyzer,
                persist=True,
            )
        except Exception as e:
            if _is_quota_error(e):
                logger.warning("backfill_reasoning: quota still exceeded, stopping")
                break
            async with session_factory() as s2:
                s2.add(row)
                row.attempts = (row.attempts or 0) + 1
                row.last_error = str(e)[:500]
                await s2.commit()
            continue

        async with session_factory() as s2:
            await s2.execute(
                delete(SignalPendingReasoning).where(SignalPendingReasoning.id == row.id)
            )
            await s2.commit()
        if result is not None:
            done += 1
    logger.info("backfill_reasoning: drained=%d", done)
    return done


@celery_app.task(name="app.workers.tasks_scoring.backfill_reasoning")
def backfill_reasoning() -> int:
    return _run_async(_backfill_reasoning_async())
