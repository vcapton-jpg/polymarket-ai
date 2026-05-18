"""Signal builder — creates Signal rows from scored event-market pairs."""

import logging
from datetime import UTC, datetime

from app.db.models import Signal
from app.scoring.feature_builder import create_feature_builder
from app.scoring.feature_dict import build_feature_dict
from app.scoring.heuristic_scorer import create_heuristic_scorer

logger = logging.getLogger(__name__)

MIN_SIGNAL_STRENGTH = 45


def _log_shadow_rejection(
    *,
    event_id: int,
    market_id: str,
    direction: str,
    market_price: float,
    rejection_reason: str,
    llm_analysis: dict | None,
) -> None:
    """Dispatch a Celery task to record this filter-rejection in the
    shadow tables. Gated behind `settings.enable_shadow_capture` so the
    pre-Sprint-3 prod baseline keeps the same behavior.

    Failures (Celery broker unreachable, task module not importable on
    a slim worker, etc.) are swallowed — the user-facing reject path is
    the source of truth, the shadow record is best-effort.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not settings.enable_shadow_capture:
        return

    try:
        from app.workers.tasks_shadow import record_shadow_signal

        record_shadow_signal.apply_async(
            kwargs={
                "event_id": event_id,
                "market_id": market_id,
                "direction": direction,
                "market_price_at_signal": float(market_price),
                "rejection_reason": rejection_reason,
                "llm_model_version": (llm_analysis or {}).get("llm_model_version"),
                # signal_score is not yet computed at the T-001/T-013
                # rejection site — that's why the column is nullable.
                "signal_score": None,
            },
            queue="default",
        )
    except Exception:
        logger.warning(
            "shadow rejection dispatch failed for market=%s reason=%s",
            market_id, rejection_reason,
            exc_info=True,
        )


def _build_score_explanation(
    score: int, strength: int, trade_q: int,
    features: dict, llm_analysis: dict | None,
) -> str:
    parts = []
    if score >= 90:
        parts.append("Exceptional signal — multiple strong factors align.")
    elif score >= 75:
        parts.append("Strong signal with high conviction.")
    elif score >= 60:
        parts.append("Moderate signal worth monitoring.")
    else:
        parts.append("Weak signal — low conviction.")

    if llm_analysis:
        imp = llm_analysis.get("impact_strength")
        conf = llm_analysis.get("llm_confidence")
        if imp is not None:
            parts.append(f"LLM impact strength: {float(imp):.2f}.")
        if conf is not None:
            parts.append(f"LLM confidence: {float(conf):.2f}.")
    fr = features.get("freshness", 0)
    if fr >= 0.9:
        parts.append("Breaking news (< 1h old).")
    elif fr >= 0.7:
        parts.append("Recent news (< 24h old).")
    conf_f = features.get("confirmation", 0)
    if conf_f >= 0.85:
        parts.append("Multiple independent sources confirm.")
    liq = features.get("liquidity", 0)
    if liq >= 0.6:
        parts.append("Good market liquidity for execution.")
    elif liq < 0.3:
        parts.append("Low liquidity — execution risk.")
    return " ".join(parts)


def _estimate_window(market_data: dict) -> str | None:
    end_date = market_data.get("end_date")
    if not end_date:
        return None
    if isinstance(end_date, str):
        try:
            end_date = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            return None
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)
    hours_left = (end_date - datetime.now(UTC)).total_seconds() / 3600
    if hours_left <= 0:
        return "Resolving now"
    if hours_left <= 24:
        return "< 24 hours"
    if hours_left <= 168:
        return "< 1 week"
    if hours_left <= 720:
        return "< 1 month"
    return "> 1 month"


def _yes_probability_explanation(direction: str, price: float | None) -> str | None:
    if price is None:
        return None
    pct = round(float(price) * 100, 1)
    d = (direction or "").upper()
    if d in ("BUY_YES", "YES"):
        if pct < 30:
            return f"Market says {pct}% YES — contrarian bet that this happens. High upside if correct."
        elif pct < 70:
            return f"Market says {pct}% YES — balanced odds. Signal sees upside above consensus."
        else:
            return f"Market says {pct}% YES — market already expects this. Limited remaining upside."
    elif d in ("BUY_NO", "NO"):
        no_pct = round(100 - pct, 1)
        if no_pct < 30:
            return f"Market says {pct}% YES — betting against consensus. High risk, high reward."
        elif no_pct < 70:
            return f"Market says {pct}% YES — signal sees it resolving NO. Moderate opportunity."
        else:
            return f"Market says {pct}% YES — NO side is favored. Signal aligns with consensus."
    return f"Market currently at {pct}% YES implied probability."


class SignalBuilder:
    def __init__(self):
        self.feature_builder = create_feature_builder()
        self.scorer = create_heuristic_scorer()

    def build_signal(
        self,
        event_id: int,
        market_id: str,
        event_data: dict,
        market_data: dict,
        llm_analysis: dict | None = None,
        cosine_score: float | None = None,
    ) -> Signal | None:
        """Build a Signal from event/market data + optional LLM analysis.

        Returns None if the score is below threshold or hard-exclusion applies.
        """
        from app.core.config import get_settings
        settings = get_settings()

        _eid = f"e{event_id}/m{market_id[:12]}"

        if cosine_score is not None and cosine_score < settings.signal_min_cosine_score:
            logger.info(
                "[%s] REJECT cosine %.3f < %.2f",
                _eid, cosine_score, settings.signal_min_cosine_score,
            )
            return None

        spread = market_data.get("spread")
        if spread is not None and float(spread) > settings.hard_exclusion_spread:
            logger.info("[%s] REJECT spread %.4f > %.2f", _eid, spread, settings.hard_exclusion_spread)
            return None

        if llm_analysis:
            direction = (llm_analysis.get("impact_direction") or "").upper()
            if direction in ("NEUTRAL", "UNCLEAR", ""):
                logger.info("[%s] REJECT direction=%s", _eid, direction)
                return None

            ambiguity = llm_analysis.get("ambiguity_score")
            if ambiguity is not None and float(ambiguity) > settings.hard_exclusion_ambiguity:
                logger.info("[%s] REJECT ambiguity %.2f > %.2f", _eid, float(ambiguity), settings.hard_exclusion_ambiguity)
                return None

            specificity = llm_analysis.get("specificity_score")
            if specificity is not None and float(specificity) < settings.hard_exclusion_min_specificity:
                logger.info("[%s] REJECT specificity %.2f < %.2f", _eid, float(specificity), settings.hard_exclusion_min_specificity)
                return None

            strength = llm_analysis.get("impact_strength")
            if strength is None or float(strength) == 0:
                logger.info("[%s] REJECT no impact_strength", _eid)
                return None

            yes_p = market_data.get("last_trade_price")
            if yes_p is not None and direction in ("BUY_YES", "BUY_NO"):
                y = float(yes_p)
                lo = settings.signal_tradeable_yes_min
                hi = settings.signal_tradeable_yes_max
                if y < lo or y > hi:
                    logger.info(
                        "[%s] REJECT price %.4f outside band [%.2f, %.2f] dir=%s",
                        _eid, y, lo, hi, direction,
                    )
                    return None

                # T-001: drop BUY_NO when the YES price is already low
                # (<0.30 default). 30 d audit (2026-05-11): 211/698 signals
                # were BUY_NO × YES<0.30 with avg move +17% AGAINST us,
                # RTP −16% to −27% depending on score bucket. Pure tail
                # short with no edge to capture. Backtest harness PR #95:
                # this filter alone moves total RTP from −1.91% to +4.68%
                # over the 30 d sample (n 699 → 488, 70% retention).
                # Feature flag exists for emergency rollback; threshold
                # configurable via `buyno_lowprice_filter_threshold`.
                if (
                    settings.enable_buyno_lowprice_filter
                    and direction == "BUY_NO"
                    and y < settings.buyno_lowprice_filter_threshold
                ):
                    logger.info(
                        "[%s] REJECT BUY_NO × low YES price %.4f < %.2f (T-001 toxic zone)",
                        _eid, y, settings.buyno_lowprice_filter_threshold,
                    )
                    _log_shadow_rejection(
                        event_id=event_id,
                        market_id=market_id,
                        direction=direction,
                        market_price=y,
                        rejection_reason="t001_low_price",
                        llm_analysis=llm_analysis,
                    )
                    return None

                # T-013: mirror of T-001 — drop BUY_NO when YES is already
                # high. Audit 2026-05-12 on 30 d (after T-001 was active):
                # BUY_NO × YES≥0.70 → n=70, RTP −4.57 %, a contrarian bet
                # against the market consensus that loses in expectation.
                # Combined backtest (T-001 + T-013): RTP −1.75 % → +6.42 %,
                # retention 60 %, t-stat 1.82 (~93 % conf). See
                # docs/measurements/buyno_band_exploration_2026-05-12.md.
                # Toggle OFF by default — flip after the v2 prompt
                # rollout has had a clean 7-day window so the two
                # interventions don't confound each other on the
                # by_llm_model_version metric.
                if (
                    settings.enable_buyno_highprice_filter
                    and direction == "BUY_NO"
                    and y >= settings.buyno_highprice_filter_threshold
                ):
                    logger.info(
                        "[%s] REJECT BUY_NO × high YES price %.4f >= %.2f (T-013 mirror zone)",
                        _eid, y, settings.buyno_highprice_filter_threshold,
                    )
                    _log_shadow_rejection(
                        event_id=event_id,
                        market_id=market_id,
                        direction=direction,
                        market_price=y,
                        rejection_reason="t013_high_price",
                        llm_analysis=llm_analysis,
                    )
                    return None

            # T-LIQUID: drop signals on operator-blacklisted categories.
            # 2026-05-12 audit: 2 categories (Hezbollah, Iran Ceasefire)
            # dragged global RTP from +3.57 % → −1.53 % over 30 d (40 / 740
            # signals = 5 % volume, but −150 to −190 % RTP each). The
            # blacklist is configurable via TOXIC_CATEGORIES_BLACKLIST
            # (CSV) so an operator can react to fast-moving news cycles
            # without a redeploy. Sits AFTER the price-band checks so
            # the shadow capture has access to the real `y` we'd have
            # entered at.
            blacklist_raw = (settings.toxic_categories_blacklist or "").strip()
            if blacklist_raw:
                blocked = {c.strip() for c in blacklist_raw.split(",") if c.strip()}
                mkt_category = market_data.get("category")
                if mkt_category and mkt_category in blocked:
                    logger.info(
                        "[%s] REJECT toxic category %r (T-LIQUID blacklist)",
                        _eid, mkt_category,
                    )
                    _log_shadow_rejection(
                        event_id=event_id,
                        market_id=market_id,
                        direction=direction,
                        market_price=y if yes_p is not None else 0.0,
                        rejection_reason=f"toxic_category:{mkt_category}",
                        llm_analysis=llm_analysis,
                    )
                    return None

            # LEVIER-1 — Spread gate. H+168 backtest (2026-05-18) proved
            # the directional edge is real (RTP +7.35 %, t=1.98, sig@95
            # at spread 0) but is entirely eaten by transaction cost:
            # ≤2 pp spread is profitable, ≥3 pp bleeds. On prod the
            # bid/ask book is bimodal — markets are either tight (<1 pp,
            # RTP +0.54 %) or have no quoted book at all (RTP −0.67 %).
            # Two knobs:
            #   * signal_max_spread_pp     — reject when a *known* spread
            #                                exceeds the threshold
            #   * reject_unknown_spread    — also reject markets with no
            #                                bid/ask book (the −0.67 %
            #                                illiquid bucket). Bigger
            #                                volume cut, bigger RTP gain.
            # Default OFF — flip after the shadow capture confirms the
            # avoided rows would indeed have bled.
            if settings.enable_max_spread_filter:
                bid = market_data.get("best_bid")
                ask = market_data.get("best_ask")
                has_book = bid is not None and ask is not None
                if has_book:
                    # Round to 4 dp (matches the NUMERIC(5,4) column) so
                    # float noise like 0.52-0.50=0.020000000000000018
                    # doesn't reject a market sitting exactly on the gate.
                    mkt_spread = round(float(ask) - float(bid), 4)
                    if mkt_spread > settings.signal_max_spread_pp:
                        logger.info(
                            "[%s] REJECT spread %.4f > %.4f (LEVIER-1 spread gate)",
                            _eid, mkt_spread, settings.signal_max_spread_pp,
                        )
                        _log_shadow_rejection(
                            event_id=event_id,
                            market_id=market_id,
                            direction=direction,
                            market_price=y if yes_p is not None else 0.0,
                            rejection_reason="spread_too_wide",
                            llm_analysis=llm_analysis,
                        )
                        return None
                elif settings.reject_unknown_spread:
                    logger.info(
                        "[%s] REJECT no bid/ask book (LEVIER-1 unknown-spread gate)",
                        _eid,
                    )
                    _log_shadow_rejection(
                        event_id=event_id,
                        market_id=market_id,
                        direction=direction,
                        market_price=y if yes_p is not None else 0.0,
                        rejection_reason="spread_unknown",
                        llm_analysis=llm_analysis,
                    )
                    return None

            # LEVIER-2 — recalibrate the LLM's over-confident P(YES).
            # H+168 calibration measurement (T-DATA): the v2 model
            # exaggerates conviction —
            #   says 0.17 → reality 0.32   (under-estimates lows)
            #   says 0.83 → reality 0.65   (over-estimates highs)
            # The direction decision rides on the gap between
            # implied_yes and the market price. An inflated implied_yes
            # manufactures phantom edge. We shrink towards 0.5 and
            # re-check: if the calibrated estimate no longer clears the
            # minimum edge vs the market, the signal only existed
            # because of the exaggeration → drop it.
            if settings.enable_llm_recalibration and yes_p is not None:
                raw_implied = (llm_analysis or {}).get("implied_yes_probability")
                if raw_implied is not None:
                    raw_implied = float(raw_implied)
                    shrink = settings.llm_calibration_shrink
                    calibrated = 0.5 + (raw_implied - 0.5) * shrink
                    edge = abs(calibrated - float(yes_p))
                    if edge < settings.min_calibrated_edge:
                        logger.info(
                            "[%s] REJECT post-calibration edge %.3f < %.2f "
                            "(LEVIER-2 raw=%.3f calib=%.3f mkt=%.3f)",
                            _eid, edge, settings.min_calibrated_edge,
                            raw_implied, calibrated, float(yes_p),
                        )
                        _log_shadow_rejection(
                            event_id=event_id,
                            market_id=market_id,
                            direction=direction,
                            market_price=float(yes_p),
                            rejection_reason="calibrated_no_edge",
                            llm_analysis=llm_analysis,
                        )
                        return None
        else:
            logger.info("[%s] REJECT no LLM analysis", _eid)
            return None

        ref_dt = (
            event_data.get("last_seen")
            or event_data.get("first_seen")
            or datetime.now(UTC)
        )

        source_count = event_data.get("unique_sources_count", 1)

        features = build_feature_dict(
            event_data=event_data,
            market_data=market_data,
            ref_dt=ref_dt,
            source_count=source_count,
            feature_builder=self.feature_builder,
        )

        llm_combined = None
        if llm_analysis:
            raw_strength = llm_analysis.get("impact_strength")
            conf = llm_analysis.get("llm_confidence")
            if raw_strength is not None and conf is not None:
                llm_combined = float(raw_strength) * 0.65 + float(conf) * 0.35

        scores = self.scorer.compute_score(features, llm_combined)
        signal_score = scores["signal_score"]
        signal_strength = scores["signal_strength"]
        trade_quality = scores["trade_quality"]

        below_threshold = False
        if signal_strength < MIN_SIGNAL_STRENGTH:
            logger.info(
                "[%s] BELOW_THRESHOLD signal_strength %d < %d (still logging)",
                _eid, signal_strength, MIN_SIGNAL_STRENGTH,
            )
            below_threshold = True

        if signal_score < settings.signal_score_threshold:
            logger.info("[%s] BELOW_THRESHOLD score %d < threshold %d (still logging)", _eid, signal_score, settings.signal_score_threshold)
            below_threshold = True

        direction = "YES"
        if llm_analysis and llm_analysis.get("impact_direction"):
            direction = llm_analysis["impact_direction"]

        confidence_label = self.scorer.derive_confidence_label(
            signal_score, source_count,
        )
        urgency_label = self.scorer.derive_urgency_label(
            signal_score, features["time_to_resolution"]
        )
        tradability_label = self.scorer.derive_tradability_label(
            features["liquidity"], features["spread"]
        )

        score_label = "exceptional" if signal_score >= 90 else "strong" if signal_score >= 75 else "moderate" if signal_score >= 60 else "monitoring"
        score_explanation = _build_score_explanation(
            signal_score, signal_strength, trade_quality, features, llm_analysis,
        )
        window_estimate = _estimate_window(market_data)
        yes_prob_explanation = _yes_probability_explanation(
            direction, market_data.get("last_trade_price"),
        )

        # T-DATA (migration 034): derive the bid-ask spread at emission.
        # `markets.spread` is NULL on 100 % of prod rows, so we compute
        # it from the live best_bid / best_ask snapshot that flowed in
        # through `_build_market_data`. None whenever either side of
        # the book is missing — the column is nullable end-to-end.
        bid = market_data.get("best_bid")
        ask = market_data.get("best_ask")
        spread_at_signal: float | None = None
        if bid is not None and ask is not None and ask >= bid:
            spread_at_signal = round(float(ask) - float(bid), 4)

        sig = Signal(
            event_id=event_id,
            market_id=market_id,
            signal_score=signal_score,
            signal_strength=signal_strength,
            trade_quality=trade_quality,
            direction=direction,
            confidence_label=confidence_label,
            urgency_label=urgency_label,
            tradability_label=tradability_label,
            market_price_at_signal=market_data.get("last_trade_price"),
            cosine_score=cosine_score,
            # T-011: stamp the producing model on every new signal so
            # admin stats can group winrate by `llm_model_version`. Pre-
            # migration-032 legacy `analysis` rows are NULL — the column
            # is nullable end-to-end, so this is safe on every path.
            llm_model_version=(llm_analysis or {}).get("llm_model_version"),
            # T-DATA (migration 034): per-signal trade-cost snapshot
            # (needed by realistic_replay to split RTP by liquidity
            # tier) and the LLM's own P(YES) estimate (needed for
            # calibration metrics). NULL acceptable on both — only v2
            # prompts emit implied_yes_probability anyway.
            spread_at_signal=spread_at_signal,
            implied_yes_probability=(llm_analysis or {}).get("implied_yes_probability"),
        )
        sig._score_label = score_label
        sig._score_explanation = score_explanation
        sig._window_estimate = window_estimate
        sig._yes_probability_explanation = yes_prob_explanation
        sig._below_threshold = below_threshold
        # Stash inputs to the heuristic so the measurement layer (record_baselines)
        # can persist them as the heuristic_v1 / heuristic_shadow rows. Without
        # these, the production scoring path cannot register predictions.
        sig._features = features
        sig._llm_combined = llm_combined
        return sig


def create_signal_builder() -> SignalBuilder:
    return SignalBuilder()


async def build_signal(
    *,
    event: dict,
    market: dict,
    articles: list[dict],
    analyzer,
    persist: bool = True,
) -> dict | None:
    """Build a signal enforcing the post-Axis-A invariant.

    Returns the assembled signal dict on success, None if the signal is rejected
    (missing reasoning or missing valid excerpts).
    When persist=True and the caller passes a session, it commits to DB.
    """
    llm = await analyzer.analyze(
        event_title=event["title"],
        event_summary=event.get("summary", ""),
        articles=articles,
        market_question=market["question"],
        market_price=float(market.get("price", 0.0)),
        market_direction_hint=market.get("direction_hint"),
    )

    if llm is None:
        logger.info(
            "signals.rejected_no_reasoning event_id=%s market_id=%s",
            event.get("id"), market.get("id"),
        )
        return None

    if not llm.get("article_excerpts"):
        logger.info(
            "signals.rejected_no_excerpts event_id=%s market_id=%s",
            event.get("id"), market.get("id"),
        )
        return None

    assembled = {
        "event_id": event["id"],
        "market_id": market["id"],
        "market_price": float(market.get("price", 0.0)),
        "catalyst": llm.get("catalyst"),
        "reasoning": llm["reasoning"],
        "llm_model_version": getattr(analyzer, "model_version", None),
        "source_tier_mix": llm.get("source_tier_mix"),
        "impact_score": llm.get("impact_score"),
        "confidence": llm.get("confidence"),
        "direction_recommendation": llm.get("direction_recommendation"),
        "article_excerpts": llm["article_excerpts"],
    }

    if persist:
        await _persist_signal(assembled, articles)
    return assembled


async def _persist_signal(assembled: dict, articles: list[dict]) -> None:
    from sqlalchemy import update

    from app.db.database import get_session_factory
    from app.db.models import EventNewsLink, Signal

    # LLM emits "YES" / "NO" / "UNCLEAR"; DB + list-endpoint filter use BUY_YES / BUY_NO.
    dir_raw = (assembled.get("direction_recommendation") or "").upper()
    if dir_raw == "YES":
        db_direction = "BUY_YES"
    elif dir_raw == "NO":
        db_direction = "BUY_NO"
    else:
        logger.info(
            "signals.rejected_unclear_direction event_id=%s market_id=%s recommendation=%r",
            assembled["event_id"], assembled["market_id"], dir_raw,
        )
        return

    import app.measurement  # noqa: F401  (side-effect: registers baselines)
    from app.measurement.pipeline import (
        record_baselines_for_signal,
        schedule_shadow_variants,
    )

    # Async path doesn't compute heuristic features (no liquidity/spread context
    # in the article-level inputs), so we derive signal_strength + trade_quality
    # from the LLM impact_score alone — same source the legacy signal_score has
    # always used. This keeps the three columns consistent (no NULLs) and stops
    # the measurement layer from blind-spotting 37% of prod signals.
    # Audit 2026-04-25 P0-1.
    derived_score = float(assembled.get("impact_score") or 0.0) * 100.0
    session_factory = get_session_factory()
    async with session_factory() as s:
        sig = Signal(
            event_id=assembled["event_id"],
            market_id=assembled["market_id"],
            signal_score=derived_score,
            signal_strength=derived_score,
            trade_quality=derived_score,
            direction=db_direction,
            market_price_at_signal=assembled.get("market_price"),
            reasoning=assembled["reasoning"],
            llm_model_version=assembled["llm_model_version"],
            source_tier_mix=assembled["source_tier_mix"],
        )
        s.add(sig)
        await s.flush()  # populate sig.id for the measurement FK

        for exc in assembled["article_excerpts"]:
            result = await s.execute(
                update(EventNewsLink)
                .where(
                    EventNewsLink.event_id == assembled["event_id"],
                    EventNewsLink.clean_id == exc["news_clean_id"],
                )
                .values(key_excerpt=exc["excerpt"], relevance_score=exc["relevance"])
            )
            if result.rowcount == 0:
                logger.warning(
                    "persist_signal: no EventNewsLink matched event_id=%s clean_id=%s — excerpt dropped",
                    assembled["event_id"], exc["news_clean_id"],
                )

        # Measurement layer — writes heuristic_v1 + 4 baselines into
        # signal_predictions. The helper internally swallows failures so a
        # broken baseline cannot abort the signal commit. NOTE: legacy async
        # path doesn't compute heuristic features/llm_combined, so the
        # optional 'heuristic_shadow' row is always skipped here (the
        # sync prod path through tasks_scoring stashes them on the Signal).
        await record_baselines_for_signal(s, signal=sig, articles=articles)

        # --- Sourcing audit (chantier #2) ------------------------------------
        try:
            from app.sourcing.prod_trace import record_prod_signal_articles
            # Prefer the richer `article_excerpts` (which carries the LLM-selected
            # quote) but fall back to the raw `articles` list when the LLM didn't
            # emit excerpts — the audit row must exist regardless.
            audit_input = assembled.get("article_excerpts") or [
                {"news_clean_id": a.get("news_clean_id"), "excerpt": None}
                for a in (articles or [])
                if a.get("news_clean_id") is not None
            ]
            await record_prod_signal_articles(
                s, signal_id=sig.id, articles=audit_input
            )
        except Exception:
            logger.exception(
                "sourcing.record_prod_signal_articles failed signal_id=%s — skipping",
                sig.id,
            )

        await s.commit()

    schedule_shadow_variants(sig.id)  # stub for chantier #3
