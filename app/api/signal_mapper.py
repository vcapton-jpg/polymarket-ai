"""Map internal Signal/Event/Market/Analysis rows to the V2 frontend shape.

The V2 frontend expects a rich, French-labelled object (see
`frontend/src/types/signal.ts`). This module is the single source of truth
for all transformations (category, direction, labels, life-percent, window
parsing, fact/source extraction). The backend routes call these helpers so
the client stays thin (no label inference, no heuristics).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from app.api.schemas_v2 import (
    FactOut,
    OutcomeOut,
    SignalCardOut,
    SignalDetailOut,
    SignalSourceOut,
    SourceOut,
    TimelineEventOut,
)
from app.db.models import (
    EventMarketAnalysis,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
    SignalOutcome,
)

# ── Category ─────────────────────────────────────────────────────────
CategoryKey = Literal[
    "geopolitics", "politics", "economics", "crypto", "sports", "science"
]

_CATEGORY_LABEL_FR: dict[CategoryKey, str] = {
    "geopolitics": "🌍 Géopolitique",
    "politics": "🏛️ Politique",
    "economics": "📈 Économie",
    "crypto": "₿ Crypto",
    "sports": "⚽ Sport",
    "science": "🔬 Science",
}

_BUCKET_TO_CATEGORY: dict[str, CategoryKey] = {
    "geopolitics": "geopolitics",
    "politics": "politics",
    "economics": "economics",
    "economy": "economics",
    "crypto": "crypto",
    "sports": "sports",
    "sport": "sports",
    "science": "science",
    "tech": "science",
    "technology": "science",
}

_CRYPTO_TERMS = (
    "bitcoin", "btc", "ethereum", "eth ", "crypto", "solana", " sol ",
    "blockchain", "defi", "nft", "coinbase", "binance",
)
_SPORTS_TERMS = (
    "nba", "nfl", "mlb", "nhl", "premier league", "champions league",
    "world cup", "super bowl", "playoff", "warriors", "lakers",
    "ucl", "fifa", "tennis", "ufc", "mma", "formula 1", " f1 ",
)
_GEO_TERMS = (
    "war", "sanctions", "ceasefire", "nato", "military", "israel",
    "gaza", "iran", "russia", "ukraine", "china", "taiwan", "lebanon",
    "hamas", "hezbollah", "invasion", "conflict", "embassy", "diplomat",
)
_POL_TERMS = (
    "president", "election", "congress", "senate", "democrat", "republican",
    "parliament", "minister", "trump", "biden", "harris", "impeach",
    "supreme court", "scotus", "pope", "prime minister",
)
_ECON_TERMS = (
    "gdp", "inflation", "interest rate", "fed ", "fomc", "recession",
    "unemployment", "stock", "s&p", "nasdaq", "tariff", "cpi ",
    "jobs report", "earnings", "ecb", "yield",
)
_SCI_TERMS = (
    "vaccine", "fda ", "clinical trial", "nasa ", "spacex", " mars ",
    " ai ", "artificial intelligence", "quantum", "climate", "pandemic",
)


def _match_terms(hay: str) -> CategoryKey | None:
    h = f" {hay.lower()} "
    if any(t in h for t in _CRYPTO_TERMS):
        return "crypto"
    if any(t in h for t in _SPORTS_TERMS):
        return "sports"
    if any(t in h for t in _GEO_TERMS):
        return "geopolitics"
    if any(t in h for t in _POL_TERMS):
        return "politics"
    if any(t in h for t in _ECON_TERMS):
        return "economics"
    if any(t in h for t in _SCI_TERMS):
        return "science"
    return None


def derive_category(
    bucket: str | None,
    question: str | None,
    event_title: str | None,
) -> tuple[CategoryKey, str]:
    """Map Event.bucket + content to (category, category_label_fr).

    Priority: explicit DB bucket > question keywords > event-title keywords
    > sensible default ("politics").
    """
    if bucket:
        cat = _BUCKET_TO_CATEGORY.get(bucket.lower())
        if cat:
            return cat, _CATEGORY_LABEL_FR[cat]
    cat = _match_terms(question or "") or _match_terms(event_title or "")
    cat = cat or "politics"
    return cat, _CATEGORY_LABEL_FR[cat]


# ── Direction ────────────────────────────────────────────────────────
def derive_direction(raw: str) -> Literal["YES", "NO"]:
    u = (raw or "").upper().strip()
    if u in ("NO", "BUY_NO") or "NO" in u:
        return "NO"
    return "YES"


# ── Labels (FR) ──────────────────────────────────────────────────────
_CONFIDENCE_FR = {
    "high": "Haute",
    "medium": "Moyenne",
    "low": "Basse",
}
_URGENCY_FR = {
    "critical": "Haute",
    "high": "Haute",
    "medium": "Moyenne",
    "low": "Basse",
}
_TRADABILITY_FR = {
    "excellent": "Bonne",
    "good": "Bonne",
    "fair": "Moyenne",
    "medium": "Moyenne",
    "poor": "Faible",
    "bad": "Faible",
}
_SCORE_LABEL_FR = {
    "exceptional": "Exceptionnel",
    "strong": "Signal fort",
    "moderate": "Actionnable",
    "actionable": "Actionnable",
    "weak": "À surveiller",
    "monitoring": "À surveiller",
}


def confidence_fr(raw: str | None) -> Literal["Haute", "Moyenne", "Basse"]:
    return _CONFIDENCE_FR.get((raw or "").lower(), "Basse")


def urgency_fr(
    raw: str | None,
) -> Literal["Haute", "Moyenne", "Basse", "Faible"]:
    return _URGENCY_FR.get((raw or "").lower(), "Faible")


def tradability_fr(
    raw: str | None,
) -> Literal["Bonne", "Moyenne", "Faible"]:
    return _TRADABILITY_FR.get((raw or "").lower(), "Moyenne")


def score_label_fr(raw: str | None, score: int) -> str:
    fr = _SCORE_LABEL_FR.get((raw or "").lower())
    if fr:
        return fr
    if score >= 90:
        return "Exceptionnel"
    if score >= 75:
        return "Signal fort"
    if score >= 60:
        return "Actionnable"
    return "À surveiller"


# ── Window / life ────────────────────────────────────────────────────
def parse_window_hours(raw: str | None) -> int:
    """Convert `window_estimate` strings ("< 1h", "2 days", "> 1 month")
    to an approximate number of hours.
    """
    if not raw:
        return 48
    s = raw.lower()
    if "month" in s:
        return 24 * 30
    if "week" in s:
        return 24 * 7
    if "day" in s or "jour" in s:
        return 48
    if "hour" in s or s.endswith("h") or "heure" in s:
        return 6
    return 48


def life_percent(created_at: datetime | None, window_hours: float) -> int:
    if not created_at:
        return 50
    now = datetime.now(UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    elapsed_h = max(0.0, (now - created_at).total_seconds() / 3600.0)
    total = max(1 / 60, float(window_hours))  # 1-minute floor avoids div-by-tiny
    remaining = 1 - min(1.0, elapsed_h / total)
    return max(5, min(100, round(remaining * 100)))


# ── Opportunity-window heuristic ────────────────────────────────────
def estimate_opportunity_window_hours(signal: Signal) -> float:
    """Estimate how long the user has to act before the trading edge
    disappears (price converges to fair value).

    This is **not** the market's resolution date — it's the diffusion
    horizon for the news catalyst. Breaking news on a thin market with a
    tier-1 source can decay in minutes; a slow-burning narrative on a
    deep, mature market may have hours of edge before arbitrage eats it.

    Multiplicative factors compose against a 6h base. Each factor maps an
    observable signal property to a unitless multiplier:

      * news age (event.first_seen → now)  — fresh news compresses; stale
        news already absorbed (lower window because edge is mostly gone).
      * urgency_label (set by scorer)      — explicit breaking-news flag.
      * source_tier_mix                    — tier-1 sources move markets
        faster than blogs.
      * market liquidity                   — deep markets arb fast; thin
        markets jump on a single bet (both compress the window).

    Floor 1 minute, ceiling 7 days, never past market resolution.
    """
    now = datetime.now(UTC)
    base_h = 6.0  # 6h baseline = "typical regional news, mid-tier source"

    # 1) News age — how stale is the catalyst?
    event = signal.event
    if event is not None and event.first_seen is not None:
        first_seen = event.first_seen
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=UTC)
        age_h = max(0.0, (now - first_seen).total_seconds() / 3600.0)
        if age_h < 0.5:        # < 30 min: very fresh, react NOW
            base_h *= 0.15
        elif age_h < 2:
            base_h *= 0.4
        elif age_h < 6:
            base_h *= 0.7
        elif age_h > 24:       # > 24h: edge is mostly priced in
            base_h *= 0.5

    # 2) Urgency label from scorer
    urgency = (signal.urgency_label or "").lower()
    if urgency == "high":
        base_h *= 0.3
    elif urgency == "low":
        base_h *= 1.5

    # 3) Top-tier source coverage. source_tier_mix is stored as shares
    #    by tasks_scoring._run_full_scoring_pipeline, e.g.
    #    {"tier_1": 0.6, "tier_2": 0.4}. We tolerate raw count dicts
    #    (legacy compute_tier_mix output) by normalising on the fly.
    tier_mix = signal.source_tier_mix or {}
    tier1_share = 0.0
    try:
        raw = tier_mix.get("tier_1", tier_mix.get("1", 0))
        raw_v = float(raw)
        if raw_v > 1.0:
            # Legacy counts dict — convert to share over the total
            total = sum(float(v) for v in tier_mix.values() if v is not None)
            tier1_share = raw_v / total if total > 0 else 0.0
        else:
            tier1_share = raw_v
    except (TypeError, ValueError):
        tier1_share = 0.0
    if tier1_share > 0.5:
        base_h *= 0.5

    # 4) Liquidity asymmetry. Both deep (>$1M) and very thin (<$5k) markets
    #    compress the window: deep markets get arbed in seconds; thin ones
    #    snap to a new equilibrium on the first opportunistic bet.
    market = signal.market
    liq = float(market.liquidity) if market and market.liquidity is not None else 0.0
    if liq > 1_000_000:
        base_h *= 0.5
    elif 0 < liq < 5_000:
        base_h *= 0.6

    # 5) Cap by market resolution if it's sooner than the diffusion horizon.
    end = market.end_date if market else None
    if end is not None:
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        hours_to_resolution = (end - now).total_seconds() / 3600.0
        if hours_to_resolution > 0:
            base_h = min(base_h, hours_to_resolution)

    # Final clamp: 1 minute floor, 7 days ceiling
    return max(1 / 60, min(base_h, 168.0))


# ── Polymarket URL + image ───────────────────────────────────────────
def polymarket_url(market_id: str) -> str:
    return f"https://polymarket.com/market/{market_id}"


def market_image_url(market: Market | None) -> str | None:
    if not market:
        return None
    return getattr(market, "image_url", None)


# ── Facts / Sources (detail) ─────────────────────────────────────────
def _build_fact(type_: str, icon: str, title: str, text: str) -> FactOut:
    return FactOut(type=type_, icon=icon, title=title, text=text)


def build_facts(
    signal: Signal,
    analysis: EventMarketAnalysis | None,
) -> list[FactOut]:
    facts: list[FactOut] = []
    reasoning = getattr(analysis, "reasoning", None) if analysis else None
    if reasoning and reasoning.strip():
        facts.append(_build_fact("main", "⚡", "Analyse IA", reasoning.strip()))
    else:
        fallback = (
            (signal.score_explanation or "").strip()
            or (getattr(signal.event, "event_summary", None) or "").strip()
            or (getattr(signal.event, "event_title", None) or "").strip()
            or "Analyse en cours."
        )
        facts.append(_build_fact("main", "⚡", "Signal principal", fallback))

    cats = getattr(analysis, "catalysts", None) if analysis else None
    if cats:
        c0 = next((c for c in cats if isinstance(c, str) and c.strip()), None)
        if c0:
            facts.append(_build_fact("context", "📌", "Catalyseur", c0.strip()))

    risks = getattr(analysis, "risks", None) if analysis else None
    if risks:
        r0 = next((r for r in risks if isinstance(r, str) and r.strip()), None)
        if r0:
            facts.append(_build_fact("risk", "⚠️", "Risque identifié", r0.strip()))

    return facts


def _tier_for(source_tier: int | None) -> int:
    t = source_tier or 2
    return 1 if t <= 1 else (2 if t == 2 else 3)


def build_sources(
    news_links: Iterable[EventNewsLink],
    now: datetime | None = None,
) -> list[SourceOut]:
    now = now or datetime.now(UTC)
    out: list[SourceOut] = []
    seen: set[str] = set()
    for link in news_links:
        clean: NewsClean | None = getattr(link, "news_clean", None)
        if not clean or not clean.news:
            continue
        news: News = clean.news
        key = (news.source_name or news.url or "").lower()
        if key in seen:
            continue
        seen.add(key)
        when = news.publish_date or news.ingestion_date
        if when and when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        minutes_ago = int(max(0, (now - when).total_seconds() // 60)) if when else 0
        out.append(
            SourceOut(
                tier=_tier_for(news.source_tier),
                name=news.source_name or "Source",
                detail=news.title[:140] if news.title else "",
                minutesAgo=minutes_ago,
            )
        )
        if len(out) >= 6:
            break
    return out


def build_detailed_sources(
    news_links: Iterable[EventNewsLink],
) -> list[SignalSourceOut]:
    """Build the rich per-article source list for the detail view.

    Orders by EventNewsLink.relevance_score (descending, NULLs last). The
    highest-scored source gets role=primary; the rest are supporting.
    """
    links = [
        link for link in news_links
        if getattr(link, "news_clean", None) and link.news_clean.news
    ]
    links.sort(
        key=lambda l: (l.relevance_score if l.relevance_score is not None else -1.0),
        reverse=True,
    )
    out: list[SignalSourceOut] = []
    for i, link in enumerate(links[:10]):
        news: News = link.news_clean.news
        publish = news.publish_date
        if publish and publish.tzinfo is None:
            publish = publish.replace(tzinfo=UTC)
        out.append(SignalSourceOut(
            newsId=news.id,
            title=news.title or "",
            url=news.url or "",
            sourceName=news.source_name or "unknown",
            sourceTier=_tier_for(news.source_tier),
            sourceWeight=(float(news.source_weight) if news.source_weight is not None else None),
            publishDate=publish.isoformat() if publish else None,
            excerpt=link.key_excerpt,
            relevanceScore=(float(link.relevance_score) if link.relevance_score is not None else None),
            role="primary" if i == 0 else "supporting",
        ))
    return out


def build_timeline(
    news_links: Iterable[EventNewsLink],
) -> list[TimelineEventOut]:
    """Flatten news_links into chronological timeline entries."""
    items: list[TimelineEventOut] = []
    for link in news_links:
        clean = getattr(link, "news_clean", None)
        if not clean or not clean.news:
            continue
        news: News = clean.news
        when = news.publish_date
        if when is None:
            # Skip entries without a publish date — an empty `at` would crash
            # the frontend's `new Date("")` + formatDistanceToNow() render.
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        items.append(TimelineEventOut(
            at=when.isoformat(),
            source=news.source_name or "unknown",
            type="news",
            headline=news.title,
        ))
    items.sort(key=lambda e: e.at, reverse=True)
    return items


# ── Top-level mappers ────────────────────────────────────────────────
def _catalyst_for(signal: Signal) -> str:
    ev = signal.event
    if ev and ev.event_summary and ev.event_summary.strip():
        return ev.event_summary.strip()
    if ev and ev.event_title and ev.event_title.strip():
        return ev.event_title.strip()
    if signal.score_explanation:
        return signal.score_explanation.strip()[:220]
    return "Contexte marché en cours de mise à jour."


def _common_fields(signal: Signal) -> dict:
    question = (signal.market.question if signal.market else None) or (
        f"Signal #{signal.id}"
    )
    event_title = signal.event.event_title if signal.event else None
    bucket = signal.event.bucket if signal.event else None
    category, category_label = derive_category(bucket, question, event_title)
    score = int(round(float(signal.signal_score)))

    # Opportunity window — diffusion horizon for the news catalyst, derived
    # from signal characteristics (news age, urgency, source tier, liquidity).
    # Returns a float so sub-hour windows (breaking news on a thin market →
    # minutes) are expressible. See estimate_opportunity_window_hours docstring.
    window_h = estimate_opportunity_window_hours(signal)

    return dict(
        id=str(signal.id),
        category=category,
        categoryLabel=category_label,
        question=question,
        direction=derive_direction(signal.direction),
        marketProbability=float(signal.market_price_at_signal)
        if signal.market_price_at_signal is not None
        else 0.5,
        windowHours=window_h,
        score=score,
        scoreLabel=score_label_fr(signal.score_label, score),
        confidence=confidence_fr(signal.confidence_label),
        urgency=urgency_fr(signal.urgency_label),
        tradability=tradability_fr(signal.tradability_label),
        catalyst=_catalyst_for(signal),
        lifePercent=life_percent(signal.created_at, window_h),
        polymarketUrl=polymarket_url(signal.market_id),
        image=market_image_url(signal.market),
        createdAt=signal.created_at,
    )


def to_signal_card(signal: Signal, sources_count: int = 0) -> SignalCardOut:
    return SignalCardOut(**_common_fields(signal), sourcesCount=sources_count)


def to_signal_detail(
    signal: Signal,
    analysis: EventMarketAnalysis | None,
    news_links: Iterable[EventNewsLink],
) -> SignalDetailOut:
    base = _common_fields(signal)
    # Materialise once — both mappers iterate news_links.
    links = list(news_links)
    sources = build_sources(links)
    return SignalDetailOut(
        **base,
        facts=build_facts(signal, analysis),
        sources=sources,
        sourcesCount=len(sources),
        reasoning=signal.reasoning,
        llmModelVersion=signal.llm_model_version,
        sourceTierMix=signal.source_tier_mix,
        detailedSources=build_detailed_sources(links),
        timeline=build_timeline(links),
        outcome=build_outcome_explainer(signal, signal.outcome),
    )


def build_outcome_explainer(
    signal: Signal, outcome: SignalOutcome | None
) -> OutcomeOut | None:
    """Build the FR-language 'outcome explainer' block shown after a signal resolves.

    Returns None when the signal hasn't resolved yet (no outcome row or no
    price_resolved). Otherwise returns an OutcomeOut with a human-readable
    learningPoint tailored to whether the signal's direction matched the
    post-resolution price move.
    """
    if outcome is None or outcome.price_resolved is None:
        return None

    base = (
        float(signal.market_price_at_signal)
        if signal.market_price_at_signal is not None
        else None
    )
    final = float(outcome.price_resolved)
    move_pct: float | None = None
    if base is not None and base > 0:
        move_pct = ((final - base) / base) * 100

    correct = outcome.direction_correct
    base_str = f"{base:.2f}" if base is not None else "inconnu"
    final_str = f"{final:.2f}"
    if correct is True:
        lp = (
            f"Le signal recommandait {signal.direction} à un prix marché de "
            f"{base_str}. Le marché a résolu à {final_str}. Direction correcte."
        )
    elif correct is False:
        lp = (
            f"Le signal recommandait {signal.direction} à un prix marché de "
            f"{base_str}. Le marché a résolu à {final_str}. Direction incorrecte — "
            f"les news n'ont pas fait bouger le prix dans le sens attendu."
        )
    else:
        lp = (
            f"Marché résolu à {final_str}. L'évaluation directionnelle du signal "
            f"n'a pas pu être déterminée."
        )

    return OutcomeOut(
        directionCorrect=correct,
        finalPrice=final,
        basePrice=base,
        movePct=move_pct,
        learningPoint=lp,
    )
