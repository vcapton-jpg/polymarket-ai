"""Map internal Signal/Event/Market/Analysis rows to the V2 frontend shape.

The V2 frontend expects a rich, French-labelled object (see
`frontend/src/types/signal.ts`). This module is the single source of truth
for all transformations (category, direction, labels, life-percent, window
parsing, fact/source extraction). The backend routes call these helpers so
the client stays thin (no label inference, no heuristics).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Literal, Optional

from app.api.schemas_v2 import FactOut, SignalCardOut, SignalDetailOut, SourceOut
from app.db.models import (
    Event,
    EventMarketAnalysis,
    EventNewsLink,
    Market,
    News,
    NewsClean,
    Signal,
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


def _match_terms(hay: str) -> Optional[CategoryKey]:
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
    bucket: Optional[str],
    question: Optional[str],
    event_title: Optional[str],
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


def confidence_fr(raw: Optional[str]) -> Literal["Haute", "Moyenne", "Basse"]:
    return _CONFIDENCE_FR.get((raw or "").lower(), "Basse")


def urgency_fr(
    raw: Optional[str],
) -> Literal["Haute", "Moyenne", "Basse", "Faible"]:
    return _URGENCY_FR.get((raw or "").lower(), "Faible")


def tradability_fr(
    raw: Optional[str],
) -> Literal["Bonne", "Moyenne", "Faible"]:
    return _TRADABILITY_FR.get((raw or "").lower(), "Moyenne")


def score_label_fr(raw: Optional[str], score: int) -> str:
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
def parse_window_hours(raw: Optional[str]) -> int:
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


def life_percent(created_at: Optional[datetime], window_hours: int) -> int:
    if not created_at:
        return 50
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    elapsed_h = max(0.0, (now - created_at).total_seconds() / 3600.0)
    total = max(1, window_hours)
    remaining = 1 - min(1.0, elapsed_h / total)
    return max(5, min(100, round(remaining * 100)))


# ── Polymarket URL + image ───────────────────────────────────────────
def polymarket_url(market_id: str) -> str:
    return f"https://polymarket.com/market/{market_id}"


def market_image_url(market: Optional[Market]) -> Optional[str]:
    if not market:
        return None
    return getattr(market, "image_url", None)


# ── Facts / Sources (detail) ─────────────────────────────────────────
def _build_fact(type_: str, icon: str, title: str, text: str) -> FactOut:
    return FactOut(type=type_, icon=icon, title=title, text=text)


def build_facts(
    signal: Signal,
    analysis: Optional[EventMarketAnalysis],
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


def _tier_for(source_tier: Optional[int]) -> int:
    t = source_tier or 2
    return 1 if t <= 1 else (2 if t == 2 else 3)


def build_sources(
    news_links: Iterable[EventNewsLink],
    now: Optional[datetime] = None,
) -> list[SourceOut]:
    now = now or datetime.now(timezone.utc)
    out: list[SourceOut] = []
    seen: set[str] = set()
    for link in news_links:
        clean: Optional[NewsClean] = getattr(link, "news_clean", None)
        if not clean or not clean.news:
            continue
        news: News = clean.news
        key = (news.source_name or news.url or "").lower()
        if key in seen:
            continue
        seen.add(key)
        when = news.publish_date or news.ingestion_date
        if when and when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
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
    window_h = parse_window_hours(signal.window_estimate)

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


def to_signal_card(signal: Signal) -> SignalCardOut:
    return SignalCardOut(**_common_fields(signal))


def to_signal_detail(
    signal: Signal,
    analysis: Optional[EventMarketAnalysis],
    news_links: Iterable[EventNewsLink],
) -> SignalDetailOut:
    base = _common_fields(signal)
    return SignalDetailOut(
        **base,
        facts=build_facts(signal, analysis),
        sources=build_sources(news_links),
    )
