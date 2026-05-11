"""Pydantic schemas for Learn & Trade routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Direction = Literal["YES", "NO"]


class PaperTradeIn(BaseModel):
    market_id: str
    signal_id: int | None = None
    direction: Direction
    stake_eur: float = Field(gt=0, le=10000)
    entry_price: float = Field(gt=0, lt=1)
    is_tutorial: bool = False


class PaperPositionOut(BaseModel):
    id: int
    market_id: str
    signal_id: int | None
    direction: Direction
    stake_eur: float
    entry_price: float
    current_price: float | None
    resolved: bool
    correct: bool | None
    pnl_eur: float | None
    is_tutorial: bool
    opened_at: datetime
    resolved_at: datetime | None

    class Config:
        from_attributes = True


class PaperPositionsOut(BaseModel):
    items: list[PaperPositionOut]


class OnboardingStatusOut(BaseModel):
    profile_done: bool
    tutorial_trades_count: int
    tutorial_done: bool
    quiz_done: bool
    budget_done: bool
    can_trade_real: bool


class QuizQuestionOut(BaseModel):
    id: str
    question: str
    choices: list[str]


class QuizSubmitIn(BaseModel):
    answers: dict[str, int]


class QuizResultOut(BaseModel):
    score: int
    total: int
    passed: bool


class BudgetSetupIn(BaseModel):
    budget_weekly_eur: float = Field(gt=0, le=500)
    max_stake_eur: float = Field(gt=0, le=100)
    age_confirmed_18: bool
    cgu_accepted: bool


class UserLimitsOut(BaseModel):
    budget_weekly_eur: float
    max_stake_eur: float
    level: int
    real_trades_count: int
    consecutive_losses: int
    week_spent_eur: float
    cooloff_until: datetime | None
    quiz_passed: bool
    age_confirmed_18: bool
