"""Pydantic response schemas for the Signal API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Health ────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded"
    version: str
    env: str
    workers: Optional[dict[str, bool]] = None


# ── Markets ───────────────────────────────────────────────────────────
class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_id: str
    question: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    end_date: Optional[datetime] = None
    active: bool
    closed: bool
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    last_trade_price: Optional[float] = None
    liquidity_pct: Optional[float] = None
    volume_24h_pct: Optional[float] = None
    updated_at: datetime


class MarketListResponse(BaseModel):
    markets: list[MarketOut]
    total: int


# ── Events ────────────────────────────────────────────────────────────
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_title: str
    event_summary: Optional[str] = None
    key_entities: Optional[list[str]] = None
    event_type: Optional[str] = None
    bucket: Optional[str] = None
    articles_count: int
    unique_sources_count: int
    first_seen: datetime
    last_seen: datetime
    processing_status: str


class EventListResponse(BaseModel):
    events: list[EventOut]
    total: int


# ── Signals ───────────────────────────────────────────────────────────
class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_id: int
    market_id: str
    signal_score: float
    signal_strength: Optional[float] = None
    trade_quality: Optional[float] = None
    direction: str
    confidence_label: Optional[str] = None
    urgency_label: Optional[str] = None
    tradability_label: Optional[str] = None
    market_price_at_signal: Optional[float] = None
    dedupe_key: Optional[str] = None
    score_label: Optional[str] = None
    score_explanation: Optional[str] = None
    window_estimate: Optional[str] = None
    yes_probability_explanation: Optional[str] = None
    event_title: Optional[str] = None
    market_question: Optional[str] = None
    created_at: datetime


class LlmAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    impact_direction: Optional[str] = None
    impact_strength: Optional[float] = None
    llm_confidence: Optional[float] = None
    specificity_score: Optional[float] = None
    catalysts: Optional[list] = None
    risks: Optional[list] = None
    reasoning: Optional[str] = None


class SignalDetailOut(SignalOut):
    event: Optional[EventOut] = None
    market: Optional[MarketOut] = None
    outcome: Optional["SignalOutcomeOut"] = None
    analysis: Optional[LlmAnalysisOut] = None


class SignalOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signal_id: int
    price_t5min: Optional[float] = None
    price_t15min: Optional[float] = None
    price_t1h: Optional[float] = None
    price_t24h: Optional[float] = None
    price_resolved: Optional[float] = None
    direction_correct: Optional[bool] = None
    outcome_label: Optional[int] = None
    move_t5min_pct: Optional[float] = None


class SignalListResponse(BaseModel):
    signals: list[SignalOut]
    total: int


# ── Analytics ─────────────────────────────────────────────────────────
class AccuracyResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    correct_signals: int
    accuracy_pct: Optional[float] = None
    by_bucket: dict[str, dict] = {}


class CostResponse(BaseModel):
    total_cost_usd: float
    total_calls: int
    by_day: list[dict] = []


# ── Pipeline health ──────────────────────────────────────────────────
class IngestionHealthResponse(BaseModel):
    sources: list[dict]
    tier1_median_lag_seconds: Optional[float] = None
    alert: bool = False


# ── Pipeline status ───────────────────────────────────────────────────
class PipelineStatusResponse(BaseModel):
    last_article_ingested: Optional[datetime] = None
    last_event_created: Optional[datetime] = None
    last_signal_created: Optional[datetime] = None
    events_pending: int = 0
    active_workers: int = 0


# ── Simulated P&L ────────────────────────────────────────────────────
class SimulatedPnlResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    simulated_pnl_pct: Optional[float] = None
    win_rate: Optional[float] = None
    wins: int = 0
    losses: int = 0
    avg_win_move_pct: Optional[float] = None
    avg_loss_move_pct: Optional[float] = None
    best_signal: Optional[dict] = None
    worst_signal: Optional[dict] = None
    by_direction: dict = {}
    by_score_tier: dict = {}


# ── Dashboard KPIs ───────────────────────────────────────────────────
class DashboardKpisResponse(BaseModel):
    total_signals: int
    signals_today: int
    resolved_signals: int
    win_rate: Optional[float] = None
    wins: int = 0
    losses: int = 0
    best_signal: Optional[dict] = None
    avg_score: Optional[float] = None
    streak: int = 0
    streak_type: str = ""


# ── Track Record (public) ───────────────────────────────────────────
class TrackRecordResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    overall_win_rate: Optional[float] = None
    weekly: list[dict] = []
    by_bucket: dict = {}
    recent_resolved: list[dict] = []


# Resolve forward refs
SignalDetailOut.model_rebuild()
