"""V2 response schemas — match `frontend/src/types/signal.ts` exactly.

These are the only signal shapes the V2 frontend consumes. Fields use
camelCase on the wire (Pydantic `alias_generator`) so the TypeScript layer
can drop them straight into the UI with zero client-side mapping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

Category = Literal[
    "geopolitics", "politics", "economics", "crypto", "sports", "science"
]
Direction = Literal["YES", "NO"]
Confidence = Literal["Haute", "Moyenne", "Basse"]
Urgency = Literal["Haute", "Moyenne", "Basse", "Faible"]
Tradability = Literal["Bonne", "Moyenne", "Faible"]
FactType = Literal["main", "risk", "context"]


class FactOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: FactType
    icon: str
    title: str
    text: str


class SourceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    tier: Literal[1, 2, 3]
    name: str
    detail: str
    minutesAgo: int


class SignalCardOut(BaseModel):
    """Shape consumed by /signals list + SignalCard component.

    `facts` and `sources` are present but empty on list responses so the
    TypeScript `Signal` contract stays uniform (SignalCard.tsx reads
    `signal.sources.length`). The detail endpoint fills them in.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    category: Category
    categoryLabel: str
    question: str
    direction: Direction
    marketProbability: float
    # Float so the opportunity window can express sub-hour values (e.g.
    # 0.083 = 5 min for a breaking-news signal on an illiquid market). The
    # frontend renders sub-hour values as "X min" via formatOpportunityWindow.
    windowHours: float
    score: int
    scoreLabel: str
    confidence: Confidence
    urgency: Urgency
    tradability: Tradability
    catalyst: str
    facts: list[FactOut] = []
    sources: list[SourceOut] = []
    # Total number of news sources backing this signal. Populated on the
    # list endpoint via a bulk COUNT(event_news_links) so SignalCard can
    # render "N sources" without paying for the full sources payload that
    # the detail endpoint serves. The detail endpoint sets this to
    # len(sources) for consistency.
    sourcesCount: int = 0
    lifePercent: int
    polymarketUrl: str
    image: str | None = None
    createdAt: datetime


class SignalSourceOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    newsId: int
    title: str
    url: str
    sourceName: str
    sourceTier: Literal[1, 2, 3]
    sourceWeight: float | None = None
    publishDate: str | None = None
    excerpt: str | None = None
    relevanceScore: float | None = None
    role: Literal["primary", "supporting"] = "supporting"


class TimelineEventOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    at: str
    source: str
    type: Literal["news", "market_move"] = "news"
    headline: str | None = None
    detail: str | None = None


class OutcomeOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    directionCorrect: bool | None = None
    finalPrice: float | None = None
    basePrice: float | None = None
    movePct: float | None = None
    learningPoint: str


class SignalDetailOut(SignalCardOut):
    """Shape consumed by /signals/:id detail page.

    Inherits all card fields and overrides `facts` + `sources` with the
    enriched content from LlmAnalysis + EventNewsLink chain.
    """

    reasoning: str | None = None
    llmModelVersion: str | None = None
    # Stored as shares per tier (e.g. {"tier_1": 0.6, "tier_2": 0.4}) by
    # tasks_scoring._run_full_scoring_pipeline. dict[str, float] (not int)
    # so 1.0/0.6 don't get truncated on the wire.
    sourceTierMix: dict[str, float] | None = None
    detailedSources: list[SignalSourceOut] = []
    timeline: list[TimelineEventOut] = []
    outcome: OutcomeOut | None = None


class SignalListOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    signals: list[SignalCardOut]
    total: int
