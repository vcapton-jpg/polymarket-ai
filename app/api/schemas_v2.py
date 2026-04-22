"""V2 response schemas — match `frontend/src/types/signal.ts` exactly.

These are the only signal shapes the V2 frontend consumes. Fields use
camelCase on the wire (Pydantic `alias_generator`) so the TypeScript layer
can drop them straight into the UI with zero client-side mapping.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

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
    windowHours: int
    score: int
    scoreLabel: str
    confidence: Confidence
    urgency: Urgency
    tradability: Tradability
    catalyst: str
    facts: list[FactOut] = []
    sources: list[SourceOut] = []
    lifePercent: int
    polymarketUrl: str
    image: Optional[str] = None
    createdAt: datetime


class SignalDetailOut(SignalCardOut):
    """Shape consumed by /signals/:id detail page.

    Inherits all card fields and overrides `facts` + `sources` with the
    enriched content from LlmAnalysis + EventNewsLink chain.
    """


class SignalListOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    signals: list[SignalCardOut]
    total: int
