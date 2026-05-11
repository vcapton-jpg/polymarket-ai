"""Pydantic response schemas for the Signal API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ── Health ────────────────────────────────────────────────────────────
class HealthResponse(BaseModel):
    status: str  # "healthy" | "degraded"
    version: str
    env: str
    workers: dict[str, bool] | None = None


# ── Markets ───────────────────────────────────────────────────────────
class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    market_id: str
    question: str
    description: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    end_date: datetime | None = None
    active: bool
    closed: bool
    volume_24h: float | None = None
    liquidity: float | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    last_trade_price: float | None = None
    liquidity_pct: float | None = None
    volume_24h_pct: float | None = None
    updated_at: datetime


class MarketListResponse(BaseModel):
    markets: list[MarketOut]
    total: int


# ── Events ────────────────────────────────────────────────────────────
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_title: str
    event_summary: str | None = None
    key_entities: list[str] | None = None
    event_type: str | None = None
    bucket: str | None = None
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
    signal_strength: float | None = None
    trade_quality: float | None = None
    direction: str
    confidence_label: str | None = None
    urgency_label: str | None = None
    tradability_label: str | None = None
    market_price_at_signal: float | None = None
    dedupe_key: str | None = None
    score_label: str | None = None
    score_explanation: str | None = None
    window_estimate: str | None = None
    yes_probability_explanation: str | None = None
    event_title: str | None = None
    market_question: str | None = None
    created_at: datetime


class LlmAnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    impact_direction: str | None = None
    impact_strength: float | None = None
    llm_confidence: float | None = None
    specificity_score: float | None = None
    catalysts: list | None = None
    risks: list | None = None
    reasoning: str | None = None


class SignalDetailOut(SignalOut):
    event: EventOut | None = None
    market: MarketOut | None = None
    outcome: Optional["SignalOutcomeOut"] = None
    analysis: LlmAnalysisOut | None = None


class SignalOutcomeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    signal_id: int
    price_t5min: float | None = None
    price_t15min: float | None = None
    price_t1h: float | None = None
    price_t24h: float | None = None
    price_resolved: float | None = None
    direction_correct: bool | None = None
    outcome_label: int | None = None
    move_t5min_pct: float | None = None


class SignalListResponse(BaseModel):
    signals: list[SignalOut]
    total: int


# ── Analytics ─────────────────────────────────────────────────────────
class AccuracyResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    correct_signals: int
    accuracy_pct: float | None = None
    by_bucket: dict[str, dict] = {}


class CostResponse(BaseModel):
    total_cost_usd: float
    total_calls: int
    by_day: list[dict] = []


# ── Pipeline health ──────────────────────────────────────────────────
class IngestionHealthResponse(BaseModel):
    sources: list[dict]
    tier1_median_lag_seconds: float | None = None
    alert: bool = False


# ── Pipeline status ───────────────────────────────────────────────────
class PipelineStatusResponse(BaseModel):
    last_article_ingested: datetime | None = None
    last_event_created: datetime | None = None
    last_signal_created: datetime | None = None
    events_pending: int = 0
    active_workers: int = 0


# ── Simulated P&L ────────────────────────────────────────────────────
class SimulatedPnlResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    simulated_pnl_pct: float | None = None
    win_rate: float | None = None
    wins: int = 0
    losses: int = 0
    avg_win_move_pct: float | None = None
    avg_loss_move_pct: float | None = None
    best_signal: dict | None = None
    worst_signal: dict | None = None
    by_direction: dict = {}
    by_score_tier: dict = {}


# ── Dashboard KPIs ───────────────────────────────────────────────────
class DashboardKpisResponse(BaseModel):
    total_signals: int
    signals_today: int
    resolved_signals: int
    win_rate: float | None = None
    wins: int = 0
    losses: int = 0
    best_signal: dict | None = None
    avg_score: float | None = None
    streak: int = 0
    streak_type: str = ""


# ── Track Record (public) ───────────────────────────────────────────
class TrackRecordResponse(BaseModel):
    total_signals: int
    resolved_signals: int
    overall_win_rate: float | None = None
    weekly: list[dict] = []
    by_bucket: dict = {}
    recent_resolved: list[dict] = []


# Resolve forward refs
SignalDetailOut.model_rebuild()
