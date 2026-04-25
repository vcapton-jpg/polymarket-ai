# Pivot "Learn & Trade" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repositionner le produit sur "jeunes qui investissent en apprenant" — onboarding tutoriel obligatoire (5 paper trades + quiz risque), trading réel gated par budget max user-imposed + cooloff automatique, gamification éducative, et durcissement légal (age gate + disclaimers).

**Architecture:**
- **Backend** : nouvelle couche `UserLimits` en middleware sur `/api/trading/trade` qui refuse tout ordre over-limit / en cooloff / sans quiz passé. Paper trading dans table séparée `paper_positions`. Outcome enrichment sur `/api/signals/:id` avec explication pédagogique post-résolution.
- **Frontend** : onboarding multi-étapes (`/welcome/tutorial`, `/welcome/quiz`, `/welcome/budget`), `OrderForm` refactoré avec slider + level-gated cap, `BudgetBar` sticky, `CooloffModal`, page `/signals/:id/outcome` obligatoire après résolution.
- **Légal** : age gate 18+ au signup, CGU + mentions légales + disclaimer "perte totale possible" checkés avant premier trade.
- **Compatibilité** : plan indépendant de l'audit mesures (5 chantiers `audit/measurement-fixes`) — tourne en parallèle.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0 async, Alembic, pytest
- Frontend: React 18 + TypeScript 5.6, Vite, Vitest, Tailwind, Framer Motion, i18next
- DB: PostgreSQL 16

**Branche:** `pivot/learn-and-trade` depuis `main`

**Règle globale TDD:** chaque tâche écrit le test d'abord, confirme qu'il fail, implémente, confirme qu'il pass, commit.

---

## Structure des fichiers

**Nouveaux fichiers backend :**
- `alembic/versions/019_user_limits_onboarding.py` — migration DB
- `app/db/models.py` — nouvelles classes `UserLimits`, `PaperPosition`, `OnboardingProgress`, `QuizAttempt`, `OutcomeView` (ajoutées à la fin)
- `app/services/user_limits.py` — logique métier limits + cooloff
- `app/api/routes/paper.py` — routes paper trading
- `app/api/routes/onboarding.py` — tutorial progress + quiz
- `app/api/schemas/learn_and_trade.py` — pydantic schemas
- `app/workers/tasks_cooloff.py` — auto-trigger cooloff sur résolution
- `tests/unit/test_user_limits.py`
- `tests/unit/test_paper_routes.py`
- `tests/unit/test_onboarding.py`
- `tests/integration/test_trading_limits.py`

**Fichiers backend modifiés :**
- `app/api/routes/trading.py` — intégrer middleware limits
- `app/api/routes/signals.py` (ou équivalent) — enrichir outcome explainer
- `app/api/main.py` — register nouveaux routers
- `app/workers/tasks_outcomes.py` — hook cooloff check après résolution

**Nouveaux fichiers frontend :**
- `frontend/src/pages/onboarding/Tutorial.tsx`
- `frontend/src/pages/onboarding/Quiz.tsx`
- `frontend/src/pages/onboarding/BudgetSetup.tsx`
- `frontend/src/pages/SignalOutcome.tsx`
- `frontend/src/components/layout/BudgetBar.tsx`
- `frontend/src/components/modals/CooloffModal.tsx`
- `frontend/src/components/modals/AgeGateModal.tsx`
- `frontend/src/components/signals/PaperOrderForm.tsx`
- `frontend/src/components/learn/OutcomeExplainer.tsx`
- `frontend/src/components/gamification/XPBadge.tsx`
- `frontend/src/components/gamification/StreakIndicator.tsx`
- `frontend/src/hooks/useUserLimits.ts`
- `frontend/src/hooks/useOnboarding.ts`
- `frontend/src/hooks/usePaperPortfolio.ts`
- `frontend/src/lib/api/limits.ts`
- `frontend/src/lib/api/paper.ts`
- `frontend/src/lib/api/onboarding.ts`
- `frontend/src/content/quiz.ts` — 3 questions du quiz
- `frontend/src/content/tutorialScenarios.ts` — 5 scénarios tutoriel
- `frontend/src/components/signals/__tests__/PaperOrderForm.test.tsx`
- `frontend/src/components/layout/__tests__/BudgetBar.test.tsx`
- `frontend/src/pages/onboarding/__tests__/Quiz.test.tsx`

**Fichiers frontend modifiés :**
- `frontend/src/App.tsx` — nouvelles routes
- `frontend/src/pages/Signup.tsx` — age gate + CGU checkbox
- `frontend/src/pages/Welcome.tsx` — rediriger vers tutorial
- `frontend/src/pages/Homepage.tsx` — hero repositionné
- `frontend/src/pages/Pricing.tsx` — Free vs Pro avec paper/real cap
- `frontend/src/pages/SignalDetail.tsx` — intégrer limits check dans OrderForm
- `frontend/src/components/signals/OrderForm.tsx` — slider, level-gated cap, limits API
- `frontend/src/components/layout/AppShell.tsx` — BudgetBar + nav vers tutorial si incomplete
- `frontend/src/locales/fr/common.json` + `en/common.json` — nouvelles clés i18n

---

## Task 1: Migration Alembic — tables Learn & Trade

**Files:**
- Create: `alembic/versions/019_user_limits_onboarding.py`
- Test: `tests/unit/test_migration_019.py`

- [ ] **Step 1: Vérifier l'ID de la dernière migration**

Run: `ls /Users/vadim/polymarket-ai/alembic/versions/ | sort | tail -3`
Expected: `018_rsshub_self_hosted_urls.py` ou plus récente.

- [ ] **Step 2: Écrire le test de migration**

Créer `tests/unit/test_migration_019.py` :

```python
"""Vérifie que migration 019 crée les 5 tables attendues avec les colonnes critiques."""

from __future__ import annotations
import pytest
from sqlalchemy import inspect
from app.db.database import get_session_factory


@pytest.mark.asyncio
async def test_migration_019_creates_tables():
    factory = get_session_factory()
    async with factory() as s:
        bind = s.bind
        inspector = await s.run_sync(lambda sync_s: inspect(sync_s.bind))
        tables = inspector.get_table_names()

    expected = {
        "user_limits",
        "paper_positions",
        "onboarding_progress",
        "quiz_attempts",
        "outcome_views",
    }
    missing = expected - set(tables)
    assert not missing, f"Tables manquantes: {missing}"


@pytest.mark.asyncio
async def test_user_limits_has_budget_columns():
    factory = get_session_factory()
    async with factory() as s:
        inspector = await s.run_sync(lambda sync_s: inspect(sync_s.bind))
        cols = {c["name"] for c in inspector.get_columns("user_limits")}

    required = {
        "user_id", "budget_weekly_eur", "max_stake_eur", "level",
        "real_trades_count", "consecutive_losses", "cooloff_until",
        "quiz_passed", "age_confirmed_18", "cgu_accepted_at",
    }
    missing = required - cols
    assert not missing, f"Colonnes manquantes: {missing}"
```

- [ ] **Step 3: Run test — doit échouer (tables absentes)**

Run: `docker compose exec app pytest tests/unit/test_migration_019.py -v`
Expected: FAIL — `Tables manquantes: {...}`

- [ ] **Step 4: Écrire la migration**

Créer `alembic/versions/019_user_limits_onboarding.py` :

```python
"""Learn & Trade tables: user_limits, paper_positions, onboarding_progress, quiz_attempts, outcome_views.

Revision ID: 019_user_limits_onboarding
Revises: 018_rsshub_self_hosted_urls
Create Date: 2026-04-23
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "019_user_limits_onboarding"
down_revision = "018_rsshub_self_hosted_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_limits",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("budget_weekly_eur", sa.Numeric(10, 2), nullable=False, server_default="20.00"),
        sa.Column("max_stake_eur", sa.Numeric(10, 2), nullable=False, server_default="10.00"),
        sa.Column("level", sa.Integer, nullable=False, server_default="1"),
        sa.Column("real_trades_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("consecutive_losses", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cooloff_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("quiz_passed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("age_confirmed_18", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("cgu_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("week_spent_eur", sa.Numeric(10, 2), nullable=False, server_default="0.00"),
        sa.Column("week_reset_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="SET NULL"), nullable=True),
        sa.Column("market_id", sa.Text, sa.ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("stake_eur", sa.Numeric(10, 2), nullable=False),
        sa.Column("entry_price", sa.Numeric(6, 4), nullable=False),
        sa.Column("current_price", sa.Numeric(6, 4), nullable=True),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("correct", sa.Boolean, nullable=True),
        sa.Column("pnl_eur", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_tutorial", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_paper_positions_user", "paper_positions", ["user_id"])

    op.create_table(
        "onboarding_progress",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("profile_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tutorial_trades_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tutorial_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("quiz_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("budget_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("unlocked_real_trading_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("answers", postgresql.JSONB, nullable=False),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_quiz_attempts_user", "quiz_attempts", ["user_id"])

    op.create_table(
        "outcome_views",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "signal_id", name="uq_outcome_views_user_signal"),
    )


def downgrade() -> None:
    op.drop_table("outcome_views")
    op.drop_table("quiz_attempts")
    op.drop_table("onboarding_progress")
    op.drop_index("ix_paper_positions_user", table_name="paper_positions")
    op.drop_table("paper_positions")
    op.drop_table("user_limits")
```

- [ ] **Step 5: Appliquer la migration**

Run: `docker compose exec app alembic upgrade head`
Expected: `Running upgrade 018_rsshub_self_hosted_urls -> 019_user_limits_onboarding`

- [ ] **Step 6: Vérifier le downgrade et re-upgrade**

Run: `docker compose exec app alembic downgrade -1 && docker compose exec app alembic upgrade head`
Expected: deux `OK`, aucune erreur.

- [ ] **Step 7: Run test — doit passer**

Run: `docker compose exec app pytest tests/unit/test_migration_019.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add alembic/versions/019_user_limits_onboarding.py tests/unit/test_migration_019.py
git commit -m "feat(pivot): add Learn & Trade DB tables (user_limits, paper_positions, onboarding_progress, quiz_attempts, outcome_views)"
```

---

## Task 2: Modèles SQLAlchemy

**Files:**
- Modify: `app/db/models.py` (ajouter 5 classes à la fin)
- Test: `tests/unit/test_models_learn_and_trade.py`

- [ ] **Step 1: Écrire le test**

Créer `tests/unit/test_models_learn_and_trade.py` :

```python
from __future__ import annotations
import pytest
from sqlalchemy import select
from app.db.database import get_session_factory
from app.db.models import (
    UserLimits, PaperPosition, OnboardingProgress, QuizAttempt, OutcomeView
)


@pytest.mark.asyncio
async def test_user_limits_defaults_and_insert():
    factory = get_session_factory()
    async with factory() as s:
        row = UserLimits(user_id=999001)
        s.add(row)
        await s.commit()
        await s.refresh(row)

    assert row.budget_weekly_eur == 20
    assert row.max_stake_eur == 10
    assert row.level == 1
    assert row.quiz_passed is False
    assert row.age_confirmed_18 is False


@pytest.mark.asyncio
async def test_paper_position_tutorial_flag():
    factory = get_session_factory()
    async with factory() as s:
        pos = PaperPosition(
            user_id=999002, market_id="0xabc", direction="YES",
            stake_eur=5.0, entry_price=0.42, is_tutorial=True,
        )
        s.add(pos)
        await s.commit()
        await s.refresh(pos)

    assert pos.is_tutorial is True
    assert pos.resolved is False
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_models_learn_and_trade.py -v`
Expected: FAIL — `ImportError: cannot import name 'UserLimits'`

- [ ] **Step 3: Ajouter les modèles**

Append à la fin de `app/db/models.py` :

```python
# ---------------------------------------------------------------------------
# Learn & Trade (2026-04-23 pivot)
# ---------------------------------------------------------------------------
class UserLimits(Base):
    __tablename__ = "user_limits"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    budget_weekly_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=20.00)
    max_stake_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=10.00)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    real_trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cooloff_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    quiz_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    age_confirmed_18: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cgu_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    week_spent_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.00)
    week_reset_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        onupdate=func.now(),
    )


class PaperPosition(Base):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="SET NULL"), nullable=True
    )
    market_id: Mapped[str] = mapped_column(
        Text, ForeignKey("markets.market_id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "YES" | "NO"
    stake_eur: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Numeric(6, 4), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    pnl_eur: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    is_tutorial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OnboardingProgress(Base):
    __tablename__ = "onboarding_progress"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    profile_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tutorial_trades_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tutorial_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quiz_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    budget_done: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unlocked_real_trading_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        onupdate=func.now(),
    )


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    answers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class OutcomeView(Base):
    __tablename__ = "outcome_views"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id", ondelete="CASCADE"), nullable=False
    )
    signal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("signals.id", ondelete="CASCADE"), nullable=False
    )
    viewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 4: Run test**

Run: `docker compose exec app pytest tests/unit/test_models_learn_and_trade.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/db/models.py tests/unit/test_models_learn_and_trade.py
git commit -m "feat(pivot): add Learn & Trade SQLAlchemy models"
```

---

## Task 3: Service `UserLimits` — logique métier

**Files:**
- Create: `app/services/user_limits.py`
- Create: `app/services/__init__.py` (si absent)
- Test: `tests/unit/test_user_limits_service.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_user_limits_service.py
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from app.db.database import get_session_factory
from app.db.models import UserLimits, OnboardingProgress
from app.services.user_limits import (
    can_trade_real, register_trade_result, TradeDecision,
)


@pytest.mark.asyncio
async def test_cannot_trade_if_quiz_not_passed():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(user_id=900001, quiz_passed=False, age_confirmed_18=True))
        s.add(OnboardingProgress(user_id=900001, tutorial_done=True, quiz_done=False, budget_done=True))
        await s.commit()

    decision = await can_trade_real(user_id=900001, stake_eur=5.0)
    assert decision.allowed is False
    assert decision.reason == "quiz_not_passed"


@pytest.mark.asyncio
async def test_cannot_trade_if_over_weekly_budget():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(
            user_id=900002, quiz_passed=True, age_confirmed_18=True,
            budget_weekly_eur=20.00, week_spent_eur=18.00,
        ))
        s.add(OnboardingProgress(user_id=900002, tutorial_done=True, quiz_done=True, budget_done=True))
        await s.commit()

    decision = await can_trade_real(user_id=900002, stake_eur=5.0)
    assert decision.allowed is False
    assert decision.reason == "over_weekly_budget"


@pytest.mark.asyncio
async def test_cannot_trade_if_over_max_stake():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(
            user_id=900003, quiz_passed=True, age_confirmed_18=True,
            max_stake_eur=10.00,
        ))
        s.add(OnboardingProgress(user_id=900003, tutorial_done=True, quiz_done=True, budget_done=True))
        await s.commit()

    decision = await can_trade_real(user_id=900003, stake_eur=15.0)
    assert decision.allowed is False
    assert decision.reason == "over_max_stake"


@pytest.mark.asyncio
async def test_cannot_trade_if_in_cooloff():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(
            user_id=900004, quiz_passed=True, age_confirmed_18=True,
            cooloff_until=datetime.now(timezone.utc) + timedelta(hours=12),
        ))
        s.add(OnboardingProgress(user_id=900004, tutorial_done=True, quiz_done=True, budget_done=True))
        await s.commit()

    decision = await can_trade_real(user_id=900004, stake_eur=5.0)
    assert decision.allowed is False
    assert decision.reason == "in_cooloff"


@pytest.mark.asyncio
async def test_register_loss_increments_consecutive_losses():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(user_id=900005, consecutive_losses=0))
        await s.commit()

    await register_trade_result(user_id=900005, won=False, stake_eur=5.0)

    async with factory() as s:
        row = await s.get(UserLimits, 900005)
    assert row.consecutive_losses == 1


@pytest.mark.asyncio
async def test_three_losses_triggers_cooloff():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(user_id=900006, consecutive_losses=2))
        await s.commit()

    await register_trade_result(user_id=900006, won=False, stake_eur=5.0)

    async with factory() as s:
        row = await s.get(UserLimits, 900006)
    assert row.consecutive_losses == 3
    assert row.cooloff_until is not None
    assert row.cooloff_until > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_win_resets_consecutive_losses():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(user_id=900007, consecutive_losses=2))
        await s.commit()

    await register_trade_result(user_id=900007, won=True, stake_eur=5.0)

    async with factory() as s:
        row = await s.get(UserLimits, 900007)
    assert row.consecutive_losses == 0
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_user_limits_service.py -v`
Expected: FAIL — module `app.services.user_limits` absent.

- [ ] **Step 3: Implémenter le service**

Créer `app/services/__init__.py` vide si absent, puis `app/services/user_limits.py` :

```python
"""UserLimits service — enforces budget + cooloff + quiz gating on real trades."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits

COOLOFF_HOURS = 24
COOLOFF_TRIGGER_LOSSES = 3


@dataclass
class TradeDecision:
    allowed: bool
    reason: Optional[str] = None
    remaining_budget_eur: Optional[float] = None


async def can_trade_real(user_id: int, stake_eur: float) -> TradeDecision:
    """Return whether this user may open a real-money trade of given stake."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        onb = await s.get(OnboardingProgress, user_id)

    if limits is None:
        return TradeDecision(allowed=False, reason="no_limits_row")

    if not limits.age_confirmed_18:
        return TradeDecision(allowed=False, reason="age_not_confirmed")

    if onb is None or not onb.tutorial_done:
        return TradeDecision(allowed=False, reason="tutorial_not_done")

    if not limits.quiz_passed:
        return TradeDecision(allowed=False, reason="quiz_not_passed")

    if onb is None or not onb.budget_done:
        return TradeDecision(allowed=False, reason="budget_not_set")

    now = datetime.now(timezone.utc)
    if limits.cooloff_until is not None and limits.cooloff_until > now:
        return TradeDecision(allowed=False, reason="in_cooloff")

    if stake_eur > float(limits.max_stake_eur):
        return TradeDecision(allowed=False, reason="over_max_stake")

    # Reset week if needed
    if limits.week_reset_at is not None and (now - limits.week_reset_at) > timedelta(days=7):
        # Will reset on next register_trade_result; for read-only decision, use current spent
        pass

    remaining = float(limits.budget_weekly_eur) - float(limits.week_spent_eur)
    if stake_eur > remaining:
        return TradeDecision(allowed=False, reason="over_weekly_budget", remaining_budget_eur=remaining)

    return TradeDecision(allowed=True, remaining_budget_eur=remaining - stake_eur)


async def register_trade_result(
    user_id: int, won: bool, stake_eur: float
) -> None:
    """Call this after outcome resolves. Updates consecutive_losses + triggers cooloff."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return

        now = datetime.now(timezone.utc)

        # Reset weekly counter if window elapsed
        if limits.week_reset_at is not None and (now - limits.week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = 0.00
            limits.week_reset_at = now

        # Only add to spent on OPEN, not on resolution. Separate function for opening below.

        if won:
            limits.consecutive_losses = 0
        else:
            limits.consecutive_losses = (limits.consecutive_losses or 0) + 1
            if limits.consecutive_losses >= COOLOFF_TRIGGER_LOSSES:
                limits.cooloff_until = now + timedelta(hours=COOLOFF_HOURS)

        await s.commit()


async def register_trade_opened(user_id: int, stake_eur: float) -> None:
    """Call when a real trade is placed. Debits weekly budget."""
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user_id)
        if limits is None:
            return
        now = datetime.now(timezone.utc)
        if limits.week_reset_at is not None and (now - limits.week_reset_at) > timedelta(days=7):
            limits.week_spent_eur = 0.00
            limits.week_reset_at = now
        limits.week_spent_eur = float(limits.week_spent_eur) + stake_eur
        limits.real_trades_count = (limits.real_trades_count or 0) + 1
        await s.commit()
```

- [ ] **Step 4: Run test — doit passer**

Run: `docker compose exec app pytest tests/unit/test_user_limits_service.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/ tests/unit/test_user_limits_service.py
git commit -m "feat(pivot): add UserLimits service with budget, cooloff, quiz gating"
```

---

## Task 4: Middleware sur `/api/trading/trade`

**Files:**
- Modify: `app/api/routes/trading.py`
- Test: `tests/integration/test_trading_limits.py`

- [ ] **Step 1: Écrire le test d'intégration**

```python
# tests/integration/test_trading_limits.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app
from app.db.database import get_session_factory
from app.db.models import UserLimits, OnboardingProgress


@pytest.mark.asyncio
async def test_trade_rejected_when_quiz_not_passed(auth_headers_for_user):
    # auth_headers_for_user is an existing conftest fixture that creates a user + returns JWT headers
    uid, headers = await auth_headers_for_user()
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(user_id=uid, age_confirmed_18=True, quiz_passed=False))
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, budget_done=True))
        await s.commit()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/trading/trade", headers=headers, json={
            "market_id": "0xtest", "direction": "YES", "amount": 5, "price": 0.5,
        })
    assert r.status_code == 403
    assert r.json()["detail"]["reason"] == "quiz_not_passed"


@pytest.mark.asyncio
async def test_trade_rejected_over_weekly_budget(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(
            user_id=uid, age_confirmed_18=True, quiz_passed=True,
            budget_weekly_eur=20, week_spent_eur=18, max_stake_eur=10,
        ))
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, budget_done=True))
        await s.commit()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/trading/trade", headers=headers, json={
            "market_id": "0xtest", "direction": "YES", "amount": 5, "price": 0.5,
        })
    assert r.status_code == 403
    assert r.json()["detail"]["reason"] == "over_weekly_budget"
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/integration/test_trading_limits.py -v`
Expected: FAIL — middleware absent, ordres passent sans check.

- [ ] **Step 3: Modifier `app/api/routes/trading.py`**

Lire `app/api/routes/trading.py` pour trouver le handler `POST /trade` (autour de la ligne où la route `/trade` est définie).

Ajouter en tête de fichier :

```python
from fastapi import HTTPException
from app.services.user_limits import can_trade_real, register_trade_opened
```

Dans le handler de `POST /trade`, **avant** tout appel au builder client, insérer :

```python
decision = await can_trade_real(user_id=current_user.id, stake_eur=float(body.amount))
if not decision.allowed:
    raise HTTPException(status_code=403, detail={"reason": decision.reason})
```

Après succès de l'ordre (avant le `return`), appeler :

```python
await register_trade_opened(user_id=current_user.id, stake_eur=float(body.amount))
```

- [ ] **Step 4: Run test — doit passer**

Run: `docker compose exec app pytest tests/integration/test_trading_limits.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add app/api/routes/trading.py tests/integration/test_trading_limits.py
git commit -m "feat(pivot): gate /api/trading/trade behind UserLimits (quiz, budget, cooloff, age)"
```

---

## Task 5: Routes paper trading

**Files:**
- Create: `app/api/routes/paper.py`
- Create: `app/api/schemas/learn_and_trade.py`
- Modify: `app/api/main.py` (register router)
- Test: `tests/unit/test_paper_routes.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_paper_routes.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app


@pytest.mark.asyncio
async def test_open_paper_position(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/paper/trade", headers=headers, json={
            "market_id": "0xabc", "signal_id": None, "direction": "YES",
            "stake_eur": 5.0, "entry_price": 0.4, "is_tutorial": True,
        })
    assert r.status_code == 200
    data = r.json()
    assert data["direction"] == "YES"
    assert data["stake_eur"] == 5.0
    assert data["is_tutorial"] is True


@pytest.mark.asyncio
async def test_list_paper_positions(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        await c.post("/api/paper/trade", headers=headers, json={
            "market_id": "0xabc", "direction": "NO",
            "stake_eur": 3.0, "entry_price": 0.7, "is_tutorial": False,
        })
        r = await c.get("/api/paper/positions", headers=headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any(p["market_id"] == "0xabc" for p in items)


@pytest.mark.asyncio
async def test_paper_trade_rejects_invalid_direction(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/paper/trade", headers=headers, json={
            "market_id": "0xabc", "direction": "MAYBE",
            "stake_eur": 5.0, "entry_price": 0.5,
        })
    assert r.status_code == 422
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_paper_routes.py -v`
Expected: FAIL — route `/api/paper/*` inexistante.

- [ ] **Step 3: Écrire les schemas**

Créer `app/api/schemas/learn_and_trade.py` :

```python
"""Pydantic schemas for Learn & Trade routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


Direction = Literal["YES", "NO"]


class PaperTradeIn(BaseModel):
    market_id: str
    signal_id: Optional[int] = None
    direction: Direction
    stake_eur: float = Field(gt=0, le=10000)
    entry_price: float = Field(gt=0, lt=1)
    is_tutorial: bool = False


class PaperPositionOut(BaseModel):
    id: int
    market_id: str
    signal_id: Optional[int]
    direction: Direction
    stake_eur: float
    entry_price: float
    current_price: Optional[float]
    resolved: bool
    correct: Optional[bool]
    pnl_eur: Optional[float]
    is_tutorial: bool
    opened_at: datetime
    resolved_at: Optional[datetime]


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
    answers: dict[str, int]  # {question_id: chosen_index}


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
    cooloff_until: Optional[datetime]
    quiz_passed: bool
    age_confirmed_18: bool
```

- [ ] **Step 4: Écrire les routes paper**

Créer `app/api/routes/paper.py` :

```python
"""Paper trading routes — no real money, uses paper_positions table."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import get_current_user
from app.api.schemas.learn_and_trade import (
    PaperPositionOut, PaperPositionsOut, PaperTradeIn,
)
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, PaperPosition, UserProfile

router = APIRouter(prefix="/paper", tags=["paper"])


@router.post("/trade", response_model=PaperPositionOut)
async def open_paper_position(
    body: PaperTradeIn,
    user: UserProfile = Depends(get_current_user),
) -> PaperPositionOut:
    factory = get_session_factory()
    async with factory() as s:
        pos = PaperPosition(
            user_id=user.id,
            signal_id=body.signal_id,
            market_id=body.market_id,
            direction=body.direction,
            stake_eur=body.stake_eur,
            entry_price=body.entry_price,
            is_tutorial=body.is_tutorial,
        )
        s.add(pos)

        # Tutorial progress
        if body.is_tutorial:
            onb = await s.get(OnboardingProgress, user.id)
            if onb is None:
                onb = OnboardingProgress(user_id=user.id)
                s.add(onb)
            onb.tutorial_trades_count = (onb.tutorial_trades_count or 0) + 1
            if onb.tutorial_trades_count >= 5:
                onb.tutorial_done = True

        await s.commit()
        await s.refresh(pos)

    return PaperPositionOut.model_validate(pos, from_attributes=True)


@router.get("/positions", response_model=PaperPositionsOut)
async def list_paper_positions(
    user: UserProfile = Depends(get_current_user),
) -> PaperPositionsOut:
    factory = get_session_factory()
    async with factory() as s:
        rows = (
            await s.execute(
                select(PaperPosition)
                .where(PaperPosition.user_id == user.id)
                .order_by(PaperPosition.opened_at.desc())
                .limit(100)
            )
        ).scalars().all()

    return PaperPositionsOut(
        items=[PaperPositionOut.model_validate(r, from_attributes=True) for r in rows]
    )
```

- [ ] **Step 5: Register le router dans `app/api/main.py`**

Lire `app/api/main.py` ligne ~69-78 pour voir le pattern. Ajouter :

```python
from app.api.routes.paper import router as paper_router
# ...
app.include_router(paper_router, prefix="/api")
```

- [ ] **Step 6: Run test**

Run: `docker compose exec app pytest tests/unit/test_paper_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add app/api/routes/paper.py app/api/schemas/learn_and_trade.py app/api/main.py tests/unit/test_paper_routes.py
git commit -m "feat(pivot): add /api/paper/* routes for paper trading"
```

---

## Task 6: Routes onboarding (tutorial status + budget setup)

**Files:**
- Create: `app/api/routes/onboarding.py`
- Modify: `app/api/main.py`
- Test: `tests/unit/test_onboarding_routes.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_onboarding_routes.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits


@pytest.mark.asyncio
async def test_get_onboarding_status_empty(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.get("/api/onboarding/status", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["tutorial_done"] is False
    assert data["quiz_done"] is False
    assert data["can_trade_real"] is False


@pytest.mark.asyncio
async def test_budget_setup_persists_and_unlocks(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    factory = get_session_factory()
    # Pre-seed: tutorial + quiz done
    async with factory() as s:
        s.add(OnboardingProgress(user_id=uid, tutorial_done=True, quiz_done=True))
        s.add(UserLimits(user_id=uid, quiz_passed=True))
        await s.commit()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/onboarding/budget", headers=headers, json={
            "budget_weekly_eur": 30.0,
            "max_stake_eur": 5.0,
            "age_confirmed_18": True,
            "cgu_accepted": True,
        })
    assert r.status_code == 200

    async with factory() as s:
        limits = await s.get(UserLimits, uid)
        onb = await s.get(OnboardingProgress, uid)
    assert float(limits.budget_weekly_eur) == 30.0
    assert float(limits.max_stake_eur) == 5.0
    assert limits.age_confirmed_18 is True
    assert limits.cgu_accepted_at is not None
    assert onb.budget_done is True
    assert onb.unlocked_real_trading_at is not None


@pytest.mark.asyncio
async def test_budget_setup_rejects_if_age_not_confirmed(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/onboarding/budget", headers=headers, json={
            "budget_weekly_eur": 30.0, "max_stake_eur": 5.0,
            "age_confirmed_18": False, "cgu_accepted": True,
        })
    assert r.status_code == 400
    assert "age_not_confirmed" in r.json()["detail"]
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_onboarding_routes.py -v`
Expected: FAIL — route absente.

- [ ] **Step 3: Écrire les routes**

Créer `app/api/routes/onboarding.py` :

```python
"""Onboarding routes — tutorial status + budget setup."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.api.schemas.learn_and_trade import (
    BudgetSetupIn, OnboardingStatusOut, UserLimitsOut,
)
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits, UserProfile

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusOut)
async def get_status(
    user: UserProfile = Depends(get_current_user),
) -> OnboardingStatusOut:
    factory = get_session_factory()
    async with factory() as s:
        onb = await s.get(OnboardingProgress, user.id)
        limits = await s.get(UserLimits, user.id)

    if onb is None:
        return OnboardingStatusOut(
            profile_done=False, tutorial_trades_count=0, tutorial_done=False,
            quiz_done=False, budget_done=False, can_trade_real=False,
        )

    can_trade = (
        onb.tutorial_done
        and onb.quiz_done
        and onb.budget_done
        and limits is not None
        and limits.age_confirmed_18
        and limits.quiz_passed
    )
    return OnboardingStatusOut(
        profile_done=onb.profile_done,
        tutorial_trades_count=onb.tutorial_trades_count,
        tutorial_done=onb.tutorial_done,
        quiz_done=onb.quiz_done,
        budget_done=onb.budget_done,
        can_trade_real=bool(can_trade),
    )


@router.post("/budget", response_model=UserLimitsOut)
async def setup_budget(
    body: BudgetSetupIn,
    user: UserProfile = Depends(get_current_user),
) -> UserLimitsOut:
    if not body.age_confirmed_18:
        raise HTTPException(status_code=400, detail="age_not_confirmed")
    if not body.cgu_accepted:
        raise HTTPException(status_code=400, detail="cgu_not_accepted")
    if body.max_stake_eur > body.budget_weekly_eur:
        raise HTTPException(status_code=400, detail="max_stake_exceeds_weekly_budget")

    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user.id)
        if limits is None:
            limits = UserLimits(user_id=user.id)
            s.add(limits)
        limits.budget_weekly_eur = body.budget_weekly_eur
        limits.max_stake_eur = body.max_stake_eur
        limits.age_confirmed_18 = True
        limits.cgu_accepted_at = datetime.now(timezone.utc)

        onb = await s.get(OnboardingProgress, user.id)
        if onb is None:
            onb = OnboardingProgress(user_id=user.id)
            s.add(onb)
        onb.budget_done = True
        if onb.tutorial_done and onb.quiz_done and limits.quiz_passed:
            onb.unlocked_real_trading_at = datetime.now(timezone.utc)

        await s.commit()
        await s.refresh(limits)

    return UserLimitsOut.model_validate(limits, from_attributes=True)
```

- [ ] **Step 4: Register dans `app/api/main.py`**

```python
from app.api.routes.onboarding import router as onboarding_router
# ...
app.include_router(onboarding_router, prefix="/api")
```

- [ ] **Step 5: Run test**

Run: `docker compose exec app pytest tests/unit/test_onboarding_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/onboarding.py app/api/main.py tests/unit/test_onboarding_routes.py
git commit -m "feat(pivot): add /api/onboarding/* routes (status + budget setup)"
```

---

## Task 7: Quiz — 3 questions hardcoded + submit

**Files:**
- Create: `app/api/routes/quiz.py`
- Create: `app/content/quiz_questions.py`
- Modify: `app/api/main.py`
- Test: `tests/unit/test_quiz_routes.py`

- [ ] **Step 1: Définir les 3 questions**

Créer `app/content/__init__.py` vide, puis `app/content/quiz_questions.py` :

```python
"""3 questions du quiz de risque. FR. Index de la bonne réponse dans `correct_idx`."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuizQuestion:
    id: str
    question: str
    choices: tuple[str, ...]
    correct_idx: int


QUIZ_QUESTIONS: tuple[QuizQuestion, ...] = (
    QuizQuestion(
        id="q1_loss_risk",
        question="Si je mise 10€ sur un marché prédictif et que ma prédiction est fausse, combien je perds au maximum ?",
        choices=(
            "Rien, c'est remboursé",
            "Une partie de la mise selon le prix",
            "La totalité de la mise (10€)",
        ),
        correct_idx=2,
    ),
    QuizQuestion(
        id="q2_signal_meaning",
        question="Un signal à score élevé signifie-t-il que je vais gagner de l'argent à coup sûr ?",
        choices=(
            "Oui, c'est garanti",
            "Non, c'est une analyse d'intérêt, jamais une garantie",
            "Oui si je mise gros",
        ),
        correct_idx=1,
    ),
    QuizQuestion(
        id="q3_budget_rule",
        question="Quelle est la règle d'or avant de miser de l'argent réel sur un marché prédictif ?",
        choices=(
            "Miser au moins 100€ pour que ça en vaille la peine",
            "Ne jamais miser plus que ce que je peux me permettre de perdre",
            "Toujours suivre le signal le plus fort",
        ),
        correct_idx=1,
    ),
)

PASS_THRESHOLD = 3  # on exige 3/3 pour passer
```

- [ ] **Step 2: Écrire le test**

```python
# tests/unit/test_quiz_routes.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits


@pytest.mark.asyncio
async def test_get_quiz_returns_3_questions(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.get("/api/quiz/questions", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert len(data["questions"]) == 3
    assert all("choices" in q for q in data["questions"])


@pytest.mark.asyncio
async def test_quiz_pass_unlocks_flag(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/quiz/submit", headers=headers, json={
            "answers": {"q1_loss_risk": 2, "q2_signal_meaning": 1, "q3_budget_rule": 1},
        })
    assert r.status_code == 200
    data = r.json()
    assert data["passed"] is True
    assert data["score"] == 3

    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, uid)
        onb = await s.get(OnboardingProgress, uid)
    assert limits.quiz_passed is True
    assert onb.quiz_done is True


@pytest.mark.asyncio
async def test_quiz_fail_does_not_unlock(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post("/api/quiz/submit", headers=headers, json={
            "answers": {"q1_loss_risk": 0, "q2_signal_meaning": 0, "q3_budget_rule": 0},
        })
    assert r.status_code == 200
    assert r.json()["passed"] is False

    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, uid)
    assert limits is None or limits.quiz_passed is False
```

- [ ] **Step 3: Écrire les routes quiz**

Créer `app/api/routes/quiz.py` :

```python
"""Quiz routes — 3 questions de risque. Pass = 3/3 pour unlock trading réel."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.schemas.learn_and_trade import (
    QuizQuestionOut, QuizResultOut, QuizSubmitIn,
)
from app.content.quiz_questions import PASS_THRESHOLD, QUIZ_QUESTIONS
from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, QuizAttempt, UserLimits, UserProfile
from pydantic import BaseModel

router = APIRouter(prefix="/quiz", tags=["quiz"])


class QuizQuestionsOut(BaseModel):
    questions: list[QuizQuestionOut]


@router.get("/questions", response_model=QuizQuestionsOut)
async def get_questions() -> QuizQuestionsOut:
    return QuizQuestionsOut(
        questions=[
            QuizQuestionOut(id=q.id, question=q.question, choices=list(q.choices))
            for q in QUIZ_QUESTIONS
        ]
    )


@router.post("/submit", response_model=QuizResultOut)
async def submit(
    body: QuizSubmitIn,
    user: UserProfile = Depends(get_current_user),
) -> QuizResultOut:
    score = 0
    for q in QUIZ_QUESTIONS:
        ans = body.answers.get(q.id)
        if ans is not None and ans == q.correct_idx:
            score += 1
    passed = score >= PASS_THRESHOLD

    factory = get_session_factory()
    async with factory() as s:
        s.add(QuizAttempt(
            user_id=user.id, answers=dict(body.answers),
            score=score, passed=passed,
        ))
        if passed:
            limits = await s.get(UserLimits, user.id)
            if limits is None:
                limits = UserLimits(user_id=user.id)
                s.add(limits)
            limits.quiz_passed = True

            onb = await s.get(OnboardingProgress, user.id)
            if onb is None:
                onb = OnboardingProgress(user_id=user.id)
                s.add(onb)
            onb.quiz_done = True
        await s.commit()

    return QuizResultOut(score=score, total=len(QUIZ_QUESTIONS), passed=passed)
```

- [ ] **Step 4: Register dans `app/api/main.py`**

```python
from app.api.routes.quiz import router as quiz_router
# ...
app.include_router(quiz_router, prefix="/api")
```

- [ ] **Step 5: Run test**

Run: `docker compose exec app pytest tests/unit/test_quiz_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/routes/quiz.py app/content/ tests/unit/test_quiz_routes.py app/api/main.py
git commit -m "feat(pivot): add quiz routes with 3 risk questions"
```

---

## Task 8: Hook cooloff trigger sur outcome resolution

**Files:**
- Modify: `app/workers/tasks_outcomes.py`
- Test: `tests/unit/test_cooloff_trigger.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_cooloff_trigger.py
from __future__ import annotations
from datetime import datetime, timezone
import pytest
from app.db.database import get_session_factory
from app.db.models import Signal, SignalOutcome, UserLimits
from app.workers.tasks_outcomes import register_user_outcome_for_signal


@pytest.mark.asyncio
async def test_losing_signal_increments_consecutive_losses_for_followers():
    """When a signal resolves and a user had opened a real position on it,
    their consecutive_losses counter increments."""
    factory = get_session_factory()
    # Set up: 1 user with a real position (real, not paper) linked to a signal
    # losing. This test assumes a `positions` row with `signal_id` column exists
    # OR a separate `real_trade_log` table. For now we simulate by calling
    # register_user_outcome_for_signal directly.

    async with factory() as s:
        s.add(UserLimits(user_id=800001, consecutive_losses=0, quiz_passed=True, age_confirmed_18=True))
        await s.commit()

    await register_user_outcome_for_signal(user_id=800001, won=False, stake_eur=5.0)

    async with factory() as s:
        row = await s.get(UserLimits, 800001)
    assert row.consecutive_losses == 1
    assert row.cooloff_until is None  # not yet, only 1 loss
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_cooloff_trigger.py -v`
Expected: FAIL — fonction `register_user_outcome_for_signal` absente.

- [ ] **Step 3: Ajouter la fonction hook dans `tasks_outcomes.py`**

Append à la fin de `app/workers/tasks_outcomes.py` :

```python
from app.services.user_limits import register_trade_result


async def register_user_outcome_for_signal(
    user_id: int, won: bool, stake_eur: float
) -> None:
    """Wire into check_resolved_markets: call once per user who had a real
    position on a resolved signal, to update their cooloff state."""
    await register_trade_result(user_id=user_id, won=won, stake_eur=stake_eur)
```

Dans `check_resolved_markets()`, après avoir déterminé `direction_correct` pour chaque signal, itérer sur les users qui ont une position réelle sur ce market et appeler `register_user_outcome_for_signal` pour chacun.

**Note d'implémentation** : la table `positions` a un `portfolio_id` mais pas de `signal_id` direct. Si l'association signal↔position n'existe pas déjà, ce hook restera dormant tant qu'elle n'est pas ajoutée. Dans ce cas, documenter dans le commit message. Pour le test unitaire, on teste la fonction isolée ; le câblage complet sera finalisé en Task 13.

- [ ] **Step 4: Run test**

Run: `docker compose exec app pytest tests/unit/test_cooloff_trigger.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/workers/tasks_outcomes.py tests/unit/test_cooloff_trigger.py
git commit -m "feat(pivot): add register_user_outcome_for_signal hook for cooloff"
```

---

## Task 9: Outcome explainer enrichment sur `/api/signals/:id`

**Files:**
- Modify: `app/api/signal_mapper.py` (ou la route qui sert `/api/signals/:id`)
- Create: `app/api/routes/outcome_views.py`
- Modify: `app/api/main.py`
- Test: `tests/unit/test_outcome_enrichment.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_outcome_enrichment.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app
from app.db.database import get_session_factory
from app.db.models import Signal, SignalOutcome


@pytest.mark.asyncio
async def test_resolved_signal_returns_outcome_explainer(seed_resolved_signal, auth_headers_for_user):
    """seed_resolved_signal is a conftest fixture that inserts a Signal with an outcome."""
    sig_id = await seed_resolved_signal(direction="BUY_YES", base_price=0.30, final_price=0.75)
    uid, headers = await auth_headers_for_user()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.get(f"/api/signals/{sig_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["outcome"] is not None
    assert data["outcome"]["directionCorrect"] is True
    assert data["outcome"]["finalPrice"] == 0.75
    assert data["outcome"]["movePct"] is not None
    assert "learningPoint" in data["outcome"]


@pytest.mark.asyncio
async def test_mark_outcome_viewed(seed_resolved_signal, auth_headers_for_user):
    sig_id = await seed_resolved_signal(direction="BUY_NO", base_price=0.60, final_price=0.20)
    uid, headers = await auth_headers_for_user()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.post(f"/api/signals/{sig_id}/outcome/viewed", headers=headers)
    assert r.status_code == 204
```

- [ ] **Step 2: Run test — doit échouer**

Run: `docker compose exec app pytest tests/unit/test_outcome_enrichment.py -v`
Expected: FAIL — champs `outcome` absent dans réponse.

- [ ] **Step 3: Enrichir le signal mapper**

Dans `app/api/signal_mapper.py`, ajouter une fonction `build_outcome_explainer(signal, outcome)` qui retourne :

```python
from typing import Optional
from app.db.models import Signal, SignalOutcome
from pydantic import BaseModel


class OutcomeOut(BaseModel):
    directionCorrect: Optional[bool]
    finalPrice: Optional[float]
    basePrice: Optional[float]
    movePct: Optional[float]
    learningPoint: str


def build_outcome_explainer(
    signal: Signal, outcome: Optional[SignalOutcome]
) -> Optional[OutcomeOut]:
    if outcome is None or outcome.price_resolved is None:
        return None

    base = float(signal.market_price_at_signal) if signal.market_price_at_signal else None
    final = float(outcome.price_resolved)
    move_pct = None
    if base and base > 0:
        move_pct = ((final - base) / base) * 100

    correct = outcome.direction_correct
    if correct is True:
        lp = (
            f"Le signal recommandait {signal.direction} à un prix marché de "
            f"{base:.2f}. Le marché a résolu à {final:.2f}. Direction correcte."
        )
    elif correct is False:
        lp = (
            f"Le signal recommandait {signal.direction} à un prix marché de "
            f"{base:.2f}. Le marché a résolu à {final:.2f}. Direction incorrecte — "
            f"les news n'ont pas fait bouger le prix dans le sens attendu."
        )
    else:
        lp = (
            f"Marché résolu à {final:.2f}. L'évaluation directionnelle du signal "
            f"n'a pas pu être déterminée."
        )

    return OutcomeOut(
        directionCorrect=correct,
        finalPrice=final,
        basePrice=base,
        movePct=move_pct,
        learningPoint=lp,
    )
```

Dans la fonction qui sert `GET /api/signals/{id}`, joindre `SignalOutcome` et appeler `build_outcome_explainer`, insérer dans la réponse sous la clé `outcome`.

- [ ] **Step 4: Créer route `POST /api/signals/{id}/outcome/viewed`**

Créer `app/api/routes/outcome_views.py` :

```python
"""Track when a user views the outcome explainer for a signal."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select

from app.api.deps import get_current_user
from app.db.database import get_session_factory
from app.db.models import OutcomeView, UserProfile

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/{signal_id}/outcome/viewed", status_code=204)
async def mark_outcome_viewed(
    signal_id: int,
    user: UserProfile = Depends(get_current_user),
) -> Response:
    factory = get_session_factory()
    async with factory() as s:
        existing = (
            await s.execute(
                select(OutcomeView).where(
                    OutcomeView.user_id == user.id,
                    OutcomeView.signal_id == signal_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            s.add(OutcomeView(user_id=user.id, signal_id=signal_id))
            await s.commit()
    return Response(status_code=204)
```

Register dans `app/api/main.py` :

```python
from app.api.routes.outcome_views import router as outcome_views_router
app.include_router(outcome_views_router, prefix="/api")
```

- [ ] **Step 5: Run test**

Run: `docker compose exec app pytest tests/unit/test_outcome_enrichment.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add app/api/signal_mapper.py app/api/routes/outcome_views.py app/api/main.py tests/unit/test_outcome_enrichment.py
git commit -m "feat(pivot): enrich GET /api/signals/:id with outcome explainer + viewed marker"
```

---

## Task 10: Frontend — API clients & hooks

**Files:**
- Create: `frontend/src/lib/api/limits.ts`
- Create: `frontend/src/lib/api/paper.ts`
- Create: `frontend/src/lib/api/onboarding.ts`
- Create: `frontend/src/hooks/useUserLimits.ts`
- Create: `frontend/src/hooks/useOnboarding.ts`
- Create: `frontend/src/hooks/usePaperPortfolio.ts`

- [ ] **Step 1: Écrire le client `limits.ts`**

```typescript
// frontend/src/lib/api/limits.ts
import { apiGet } from "./client"

export type UserLimits = {
  budgetWeeklyEur: number
  maxStakeEur: number
  level: number
  realTradesCount: number
  consecutiveLosses: number
  weekSpentEur: number
  cooloffUntil: string | null
  quizPassed: boolean
  ageConfirmed18: boolean
}

type WireUserLimits = {
  budget_weekly_eur: number
  max_stake_eur: number
  level: number
  real_trades_count: number
  consecutive_losses: number
  week_spent_eur: number
  cooloff_until: string | null
  quiz_passed: boolean
  age_confirmed_18: boolean
}

function hydrate(w: WireUserLimits): UserLimits {
  return {
    budgetWeeklyEur: w.budget_weekly_eur,
    maxStakeEur: w.max_stake_eur,
    level: w.level,
    realTradesCount: w.real_trades_count,
    consecutiveLosses: w.consecutive_losses,
    weekSpentEur: w.week_spent_eur,
    cooloffUntil: w.cooloff_until,
    quizPassed: w.quiz_passed,
    ageConfirmed18: w.age_confirmed_18,
  }
}

export async function fetchUserLimits(): Promise<UserLimits> {
  const wire = await apiGet<WireUserLimits>("/me/limits")
  return hydrate(wire)
}
```

- [ ] **Step 2: Écrire le client `paper.ts`**

```typescript
// frontend/src/lib/api/paper.ts
import { apiGet, apiPost } from "./client"

export type PaperPosition = {
  id: number
  marketId: string
  signalId: number | null
  direction: "YES" | "NO"
  stakeEur: number
  entryPrice: number
  currentPrice: number | null
  resolved: boolean
  correct: boolean | null
  pnlEur: number | null
  isTutorial: boolean
  openedAt: string
  resolvedAt: string | null
}

type WirePaperPosition = {
  id: number
  market_id: string
  signal_id: number | null
  direction: "YES" | "NO"
  stake_eur: number
  entry_price: number
  current_price: number | null
  resolved: boolean
  correct: boolean | null
  pnl_eur: number | null
  is_tutorial: boolean
  opened_at: string
  resolved_at: string | null
}

function hydrate(w: WirePaperPosition): PaperPosition {
  return {
    id: w.id,
    marketId: w.market_id,
    signalId: w.signal_id,
    direction: w.direction,
    stakeEur: w.stake_eur,
    entryPrice: w.entry_price,
    currentPrice: w.current_price,
    resolved: w.resolved,
    correct: w.correct,
    pnlEur: w.pnl_eur,
    isTutorial: w.is_tutorial,
    openedAt: w.opened_at,
    resolvedAt: w.resolved_at,
  }
}

export async function openPaperTrade(input: {
  marketId: string
  signalId?: number | null
  direction: "YES" | "NO"
  stakeEur: number
  entryPrice: number
  isTutorial?: boolean
}): Promise<PaperPosition> {
  const wire = await apiPost<WirePaperPosition>("/paper/trade", {
    market_id: input.marketId,
    signal_id: input.signalId ?? null,
    direction: input.direction,
    stake_eur: input.stakeEur,
    entry_price: input.entryPrice,
    is_tutorial: input.isTutorial ?? false,
  })
  return hydrate(wire)
}

export async function fetchPaperPositions(): Promise<PaperPosition[]> {
  const r = await apiGet<{ items: WirePaperPosition[] }>("/paper/positions")
  return r.items.map(hydrate)
}
```

- [ ] **Step 3: Écrire le client `onboarding.ts`**

```typescript
// frontend/src/lib/api/onboarding.ts
import { apiGet, apiPost } from "./client"

export type OnboardingStatus = {
  profileDone: boolean
  tutorialTradesCount: number
  tutorialDone: boolean
  quizDone: boolean
  budgetDone: boolean
  canTradeReal: boolean
}

type WireOnboardingStatus = {
  profile_done: boolean
  tutorial_trades_count: number
  tutorial_done: boolean
  quiz_done: boolean
  budget_done: boolean
  can_trade_real: boolean
}

function hydrateStatus(w: WireOnboardingStatus): OnboardingStatus {
  return {
    profileDone: w.profile_done,
    tutorialTradesCount: w.tutorial_trades_count,
    tutorialDone: w.tutorial_done,
    quizDone: w.quiz_done,
    budgetDone: w.budget_done,
    canTradeReal: w.can_trade_real,
  }
}

export async function fetchOnboardingStatus(): Promise<OnboardingStatus> {
  const wire = await apiGet<WireOnboardingStatus>("/onboarding/status")
  return hydrateStatus(wire)
}

export async function submitBudget(input: {
  budgetWeeklyEur: number
  maxStakeEur: number
  ageConfirmed18: boolean
  cguAccepted: boolean
}): Promise<void> {
  await apiPost("/onboarding/budget", {
    budget_weekly_eur: input.budgetWeeklyEur,
    max_stake_eur: input.maxStakeEur,
    age_confirmed_18: input.ageConfirmed18,
    cgu_accepted: input.cguAccepted,
  })
}

export type QuizQuestion = { id: string; question: string; choices: string[] }
export async function fetchQuizQuestions(): Promise<QuizQuestion[]> {
  const r = await apiGet<{ questions: QuizQuestion[] }>("/quiz/questions")
  return r.questions
}

export async function submitQuiz(answers: Record<string, number>): Promise<{
  score: number; total: number; passed: boolean
}> {
  return apiPost("/quiz/submit", { answers })
}
```

- [ ] **Step 4: Écrire les hooks**

```typescript
// frontend/src/hooks/useUserLimits.ts
import { useQuery } from "@tanstack/react-query"
import { fetchUserLimits } from "@/lib/api/limits"

export function useUserLimits() {
  return useQuery({
    queryKey: ["user-limits"],
    queryFn: fetchUserLimits,
    staleTime: 30_000,
  })
}
```

```typescript
// frontend/src/hooks/useOnboarding.ts
import { useQuery } from "@tanstack/react-query"
import { fetchOnboardingStatus } from "@/lib/api/onboarding"

export function useOnboardingStatus() {
  return useQuery({
    queryKey: ["onboarding-status"],
    queryFn: fetchOnboardingStatus,
    staleTime: 10_000,
  })
}
```

```typescript
// frontend/src/hooks/usePaperPortfolio.ts
import { useQuery } from "@tanstack/react-query"
import { fetchPaperPositions } from "@/lib/api/paper"

export function usePaperPortfolio() {
  return useQuery({
    queryKey: ["paper-positions"],
    queryFn: fetchPaperPositions,
    staleTime: 15_000,
  })
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api/limits.ts frontend/src/lib/api/paper.ts frontend/src/lib/api/onboarding.ts frontend/src/hooks/useUserLimits.ts frontend/src/hooks/useOnboarding.ts frontend/src/hooks/usePaperPortfolio.ts
git commit -m "feat(pivot): frontend API clients + hooks for limits, paper, onboarding"
```

---

## Task 11: Signup — age gate + CGU

**Files:**
- Modify: `frontend/src/pages/Signup.tsx`
- Create: `frontend/src/components/modals/AgeGateModal.tsx`
- Test: `frontend/src/pages/__tests__/Signup.test.tsx` (nouveau)

- [ ] **Step 1: Écrire le test frontend**

```tsx
// frontend/src/pages/__tests__/Signup.test.tsx
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { describe, expect, it, vi } from "vitest"
import Signup from "../Signup"

vi.mock("@/lib/api/auth", () => ({
  registerApi: vi.fn().mockResolvedValue({ token: "t", user: { id: 1 } }),
  setToken: vi.fn(),
  fetchMe: vi.fn().mockResolvedValue({ id: 1 }),
}))

function renderSignup() {
  return render(
    <MemoryRouter>
      <Signup />
    </MemoryRouter>,
  )
}

describe("Signup — age gate + CGU", () => {
  it("disables submit when age_18 checkbox is unchecked", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "password123")
    const submit = screen.getByRole("button", { name: /créer|signup|s'inscrire/i })
    expect(submit).toBeDisabled()
  })

  it("enables submit when age_18 + CGU are both checked", async () => {
    renderSignup()
    await userEvent.type(screen.getByLabelText(/email/i), "a@b.com")
    await userEvent.type(screen.getByLabelText(/mot de passe/i), "password123")
    await userEvent.click(screen.getByLabelText(/j'ai 18 ans/i))
    await userEvent.click(screen.getByLabelText(/j'accepte les cgu/i))
    const submit = screen.getByRole("button", { name: /créer|signup|s'inscrire/i })
    expect(submit).not.toBeDisabled()
  })
})
```

- [ ] **Step 2: Run — doit échouer**

Run: `cd frontend && npm run test -- Signup.test.tsx`
Expected: FAIL — labels absents ou submit toujours enabled.

- [ ] **Step 3: Modifier `Signup.tsx`**

Ajouter deux checkboxes juste avant le bouton submit, gérer leur state local `age18` et `cguAccepted`, et `disabled={loading || !age18 || !cguAccepted || ...}` sur le bouton :

```tsx
const [age18, setAge18] = useState(false)
const [cguAccepted, setCguAccepted] = useState(false)

// ...dans le JSX, avant le bouton submit :
<label className="flex items-start gap-2 text-sm">
  <input
    type="checkbox"
    checked={age18}
    onChange={e => setAge18(e.target.checked)}
    className="mt-0.5"
    aria-label="J'ai 18 ans ou plus"
  />
  <span>J'ai 18 ans ou plus. Les marchés prédictifs peuvent me faire perdre de l'argent.</span>
</label>
<label className="flex items-start gap-2 text-sm">
  <input
    type="checkbox"
    checked={cguAccepted}
    onChange={e => setCguAccepted(e.target.checked)}
    className="mt-0.5"
    aria-label="J'accepte les CGU"
  />
  <span>
    J'accepte les <a href="/cgu" target="_blank" className="underline">CGU</a> et la{" "}
    <a href="/risques" target="_blank" className="underline">politique de risque</a>.
  </span>
</label>
```

Sur le bouton submit, ajouter `disabled={loading || !age18 || !cguAccepted || ...}`.

- [ ] **Step 4: Run test — doit passer**

Run: `cd frontend && npm run test -- Signup.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Signup.tsx frontend/src/pages/__tests__/Signup.test.tsx
git commit -m "feat(pivot): age gate 18+ and CGU checkbox on signup"
```

---

## Task 12: Onboarding — Tutorial page (5 paper trades)

**Files:**
- Create: `frontend/src/pages/onboarding/Tutorial.tsx`
- Create: `frontend/src/content/tutorialScenarios.ts`
- Modify: `frontend/src/App.tsx` (ajouter la route)
- Modify: `frontend/src/pages/Welcome.tsx` (rediriger vers `/welcome/tutorial` à la fin)

- [ ] **Step 1: Définir les 5 scénarios**

Créer `frontend/src/content/tutorialScenarios.ts` :

```typescript
export type TutorialScenario = {
  id: string
  marketId: string
  question: string
  category: string
  entryPrice: number
  narrative: string
  correctDirection: "YES" | "NO"
  explanation: string
}

export const TUTORIAL_SCENARIOS: TutorialScenario[] = [
  {
    id: "s1",
    marketId: "tutorial_1",
    question: "L'équipe X va-t-elle gagner le championnat ?",
    category: "sports",
    entryPrice: 0.35,
    narrative:
      "L'équipe X vient de gagner 4 matchs d'affilée. Le marché a bougé de 0.20 à 0.35 en 48h.",
    correctDirection: "YES",
    explanation:
      "Quand le momentum news + marché s'alignent (4 victoires + hausse de prix), la direction YES est souvent la bonne. Attention cependant : le prix a déjà bougé, une partie du gain potentiel est déjà prise.",
  },
  {
    id: "s2",
    marketId: "tutorial_2",
    question: "Le gouvernement Y va-t-il passer la loi avant fin d'année ?",
    category: "politics",
    entryPrice: 0.78,
    narrative:
      "Le marché est à 0.78. Une news tombe : 3 députés clés annoncent qu'ils voteront contre.",
    correctDirection: "NO",
    explanation:
      "Une news négative sur un marché déjà haut (0.78) crée souvent un retour vers le bas. BUY_NO est justifié quand le marché semblait trop confiant.",
  },
  {
    id: "s3",
    marketId: "tutorial_3",
    question: "Le prix du bitcoin dépassera-t-il 100k$ ce mois ?",
    category: "crypto",
    entryPrice: 0.50,
    narrative:
      "Le marché est pile à 0.50. Une seule news tier-3 dit que 'Elon pense que oui'. Aucune autre source.",
    correctDirection: "NO",
    explanation:
      "Une source unique, tier-3, sur un marché à 0.50 = signal faible. L'habitude du marché quand l'info est mince = il ne bouge pas vraiment, souvent léger retour à la moyenne. Ne jamais trader sur une source unique.",
  },
  {
    id: "s4",
    marketId: "tutorial_4",
    question: "Le taux directeur de la BCE va-t-il baisser en juin ?",
    category: "economics",
    entryPrice: 0.42,
    narrative:
      "3 sources tier-1 (Bloomberg, Reuters, FT) rapportent dans la même heure que Lagarde a laissé entendre une baisse. Prix monte de 0.30 à 0.42.",
    correctDirection: "YES",
    explanation:
      "3 sources tier-1 convergentes = signal fort. Le prix a bougé mais reste dans une zone où il y a de la marge (0.42 → potentiellement 0.70+ si confirmé). Bon setup.",
  },
  {
    id: "s5",
    marketId: "tutorial_5",
    question: "Le pays Z va-t-il ratifier l'accord climat avant la COP ?",
    category: "geopolitics",
    entryPrice: 0.88,
    narrative:
      "Le marché est à 0.88. Une source tier-2 rapporte une déclaration du premier ministre : 'on est presque prêts'.",
    correctDirection: "NO",
    explanation:
      "Un marché à 0.88 a déjà pricé l'accord. Même une news positive n'apporte quasi rien (peu d'upside). Un signal à ce niveau de prix a souvent un mauvais rapport risque/rendement — on s'abstient ou on prend le contre (BUY_NO) en pariant que la résolution finale sera moins nette que prévu.",
  },
]
```

- [ ] **Step 2: Écrire la page Tutorial**

```tsx
// frontend/src/pages/onboarding/Tutorial.tsx
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { TUTORIAL_SCENARIOS } from "@/content/tutorialScenarios"
import { openPaperTrade } from "@/lib/api/paper"

export default function Tutorial() {
  const [idx, setIdx] = useState(0)
  const [lastResult, setLastResult] = useState<"correct" | "incorrect" | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()
  const scenario = TUTORIAL_SCENARIOS[idx]

  async function choose(direction: "YES" | "NO") {
    if (submitting || !scenario) return
    setSubmitting(true)
    try {
      await openPaperTrade({
        marketId: scenario.marketId,
        direction,
        stakeEur: 5,
        entryPrice: scenario.entryPrice,
        isTutorial: true,
      })
      setLastResult(direction === scenario.correctDirection ? "correct" : "incorrect")
    } finally {
      setSubmitting(false)
    }
  }

  function next() {
    setLastResult(null)
    if (idx + 1 >= TUTORIAL_SCENARIOS.length) {
      navigate("/welcome/quiz")
    } else {
      setIdx(idx + 1)
    }
  }

  if (!scenario) return null

  return (
    <div className="mx-auto max-w-2xl p-6 space-y-6">
      <h1 className="text-2xl font-bold">
        Tutoriel — scénario {idx + 1} / {TUTORIAL_SCENARIOS.length}
      </h1>
      <div className="rounded-xl border border-border bg-card p-6 space-y-3">
        <p className="text-xs uppercase text-muted-foreground">{scenario.category}</p>
        <h2 className="text-lg font-semibold">{scenario.question}</h2>
        <p className="text-sm">Prix actuel YES : {(scenario.entryPrice * 100).toFixed(0)}%</p>
        <p className="text-sm text-muted-foreground">{scenario.narrative}</p>
      </div>

      {lastResult === null ? (
        <div className="flex gap-3">
          <button
            onClick={() => choose("YES")}
            disabled={submitting}
            className="flex-1 rounded-lg bg-signal-yes/20 hover:bg-signal-yes/30 py-3 font-semibold"
          >
            Parier YES (5€ virtuels)
          </button>
          <button
            onClick={() => choose("NO")}
            disabled={submitting}
            className="flex-1 rounded-lg bg-signal-no/20 hover:bg-signal-no/30 py-3 font-semibold"
          >
            Parier NO (5€ virtuels)
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className={`rounded-lg p-4 ${lastResult === "correct" ? "bg-signal-yes/10" : "bg-signal-no/10"}`}>
            <p className="font-semibold">
              {lastResult === "correct" ? "✓ Bonne lecture" : "✗ Leçon à retenir"}
            </p>
            <p className="text-sm mt-2">{scenario.explanation}</p>
          </div>
          <button
            onClick={next}
            className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold"
          >
            {idx + 1 >= TUTORIAL_SCENARIOS.length ? "Passer au quiz →" : "Scénario suivant →"}
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Ajouter la route dans `App.tsx`**

```tsx
const Tutorial = lazy(() => import("./pages/onboarding/Tutorial"))
// ...
<Route path="/welcome/tutorial" element={<RequireAuth><Tutorial /></RequireAuth>} />
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/onboarding/Tutorial.tsx frontend/src/content/tutorialScenarios.ts frontend/src/App.tsx
git commit -m "feat(pivot): tutorial flow with 5 paper trade scenarios"
```

---

## Task 13: Onboarding — Quiz page

**Files:**
- Create: `frontend/src/pages/onboarding/Quiz.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/pages/onboarding/__tests__/Quiz.test.tsx`

- [ ] **Step 1: Écrire le test**

```tsx
// frontend/src/pages/onboarding/__tests__/Quiz.test.tsx
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import Quiz from "../Quiz"

vi.mock("@/lib/api/onboarding", () => ({
  fetchQuizQuestions: vi.fn().mockResolvedValue([
    { id: "q1", question: "Q1?", choices: ["A", "B", "C"] },
    { id: "q2", question: "Q2?", choices: ["X", "Y"] },
    { id: "q3", question: "Q3?", choices: ["1", "2", "3"] },
  ]),
  submitQuiz: vi.fn().mockResolvedValue({ score: 3, total: 3, passed: true }),
}))

function renderQuiz() {
  const qc = new QueryClient()
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <Quiz />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe("Quiz", () => {
  it("renders all 3 questions after load", async () => {
    renderQuiz()
    await waitFor(() => expect(screen.getByText("Q1?")).toBeInTheDocument())
    expect(screen.getByText("Q2?")).toBeInTheDocument()
    expect(screen.getByText("Q3?")).toBeInTheDocument()
  })

  it("disables submit until all questions answered", async () => {
    renderQuiz()
    await waitFor(() => screen.getByText("Q1?"))
    const submit = screen.getByRole("button", { name: /valider/i })
    expect(submit).toBeDisabled()
  })
})
```

- [ ] **Step 2: Run — doit échouer**

Run: `cd frontend && npm run test -- Quiz.test.tsx`
Expected: FAIL — page absente.

- [ ] **Step 3: Écrire la page**

```tsx
// frontend/src/pages/onboarding/Quiz.tsx
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { fetchQuizQuestions, submitQuiz } from "@/lib/api/onboarding"

export default function Quiz() {
  const [answers, setAnswers] = useState<Record<string, number>>({})
  const [result, setResult] = useState<{ score: number; passed: boolean } | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const navigate = useNavigate()

  const { data: questions = [] } = useQuery({
    queryKey: ["quiz-questions"],
    queryFn: fetchQuizQuestions,
  })

  async function onSubmit() {
    if (submitting) return
    setSubmitting(true)
    try {
      const r = await submitQuiz(answers)
      setResult({ score: r.score, passed: r.passed })
      if (r.passed) setTimeout(() => navigate("/welcome/budget"), 1500)
    } finally {
      setSubmitting(false)
    }
  }

  const allAnswered = questions.length > 0 && questions.every(q => q.id in answers)

  return (
    <div className="mx-auto max-w-2xl p-6 space-y-6">
      <h1 className="text-2xl font-bold">Quiz risque — 3 questions</h1>
      <p className="text-sm text-muted-foreground">
        Il faut 3/3 pour débloquer le trading réel. Tu peux recommencer si tu échoues.
      </p>

      {questions.map((q, qi) => (
        <div key={q.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
          <p className="font-semibold">{qi + 1}. {q.question}</p>
          <div className="flex flex-col gap-2">
            {q.choices.map((c, ci) => (
              <label key={ci} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={q.id}
                  checked={answers[q.id] === ci}
                  onChange={() => setAnswers({ ...answers, [q.id]: ci })}
                />
                <span className="text-sm">{c}</span>
              </label>
            ))}
          </div>
        </div>
      ))}

      <button
        onClick={onSubmit}
        disabled={!allAnswered || submitting || result?.passed === true}
        className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold disabled:opacity-50"
      >
        Valider
      </button>

      {result && (
        <div className={`rounded-lg p-4 ${result.passed ? "bg-signal-yes/10" : "bg-signal-no/10"}`}>
          <p className="font-semibold">
            {result.passed ? `✓ Bravo, ${result.score}/3. Tu débloques le trading réel.` : `✗ ${result.score}/3. Relis les questions et retente.`}
          </p>
          {!result.passed && (
            <button
              onClick={() => setResult(null)}
              className="mt-3 text-sm underline"
            >
              Recommencer
            </button>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Ajouter la route dans `App.tsx`**

```tsx
const Quiz = lazy(() => import("./pages/onboarding/Quiz"))
// ...
<Route path="/welcome/quiz" element={<RequireAuth><Quiz /></RequireAuth>} />
```

- [ ] **Step 5: Run test**

Run: `cd frontend && npm run test -- Quiz.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/onboarding/Quiz.tsx frontend/src/pages/onboarding/__tests__/Quiz.test.tsx frontend/src/App.tsx
git commit -m "feat(pivot): quiz page with 3 risk questions"
```

---

## Task 14: Onboarding — BudgetSetup page

**Files:**
- Create: `frontend/src/pages/onboarding/BudgetSetup.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Écrire la page**

```tsx
// frontend/src/pages/onboarding/BudgetSetup.tsx
import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { submitBudget } from "@/lib/api/onboarding"

export default function BudgetSetup() {
  const [weekly, setWeekly] = useState(20)
  const [maxStake, setMaxStake] = useState(5)
  const [ageOk, setAgeOk] = useState(false)
  const [cguOk, setCguOk] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const navigate = useNavigate()

  async function onSubmit() {
    if (submitting) return
    setErr(null)
    if (maxStake > weekly) {
      setErr("Le stake max ne peut pas dépasser le budget hebdomadaire.")
      return
    }
    setSubmitting(true)
    try {
      await submitBudget({
        budgetWeeklyEur: weekly,
        maxStakeEur: maxStake,
        ageConfirmed18: ageOk,
        cguAccepted: cguOk,
      })
      navigate("/signals")
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Erreur")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-md p-6 space-y-6">
      <h1 className="text-2xl font-bold">Définis tes limites</h1>
      <p className="text-sm text-muted-foreground">
        Tu peux modifier ces limites plus tard dans Settings. Elles sont appliquées côté serveur.
      </p>

      <div className="space-y-2">
        <label className="text-sm font-semibold">Budget hebdomadaire (€)</label>
        <input
          type="range" min={5} max={200} step={5}
          value={weekly}
          onChange={e => setWeekly(Number(e.target.value))}
          className="w-full"
        />
        <p className="text-xl font-bold">{weekly}€ / semaine</p>
      </div>

      <div className="space-y-2">
        <label className="text-sm font-semibold">Mise max par trade (€)</label>
        <input
          type="range" min={1} max={50} step={1}
          value={maxStake}
          onChange={e => setMaxStake(Number(e.target.value))}
          className="w-full"
        />
        <p className="text-xl font-bold">{maxStake}€ max / trade</p>
      </div>

      <div className="rounded-lg bg-obsidian-800 p-3 text-xs text-muted-foreground">
        Règle : tu ne pourras jamais miser plus de {maxStake}€ sur un trade, ni plus de {weekly}€ au total sur la semaine glissante. Passée cette limite, l'API refuse tes ordres.
      </div>

      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={ageOk} onChange={e => setAgeOk(e.target.checked)} className="mt-0.5" />
        <span>Je confirme avoir 18 ans ou plus.</span>
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" checked={cguOk} onChange={e => setCguOk(e.target.checked)} className="mt-0.5" />
        <span>J'accepte les <a href="/cgu" target="_blank" className="underline">CGU</a> et comprends que je peux perdre la totalité de ma mise.</span>
      </label>

      {err && <p className="text-sm text-signal-no">{err}</p>}

      <button
        onClick={onSubmit}
        disabled={submitting || !ageOk || !cguOk}
        className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold disabled:opacity-50"
      >
        Débloquer le trading réel
      </button>
    </div>
  )
}
```

- [ ] **Step 2: Route dans App.tsx**

```tsx
const BudgetSetup = lazy(() => import("./pages/onboarding/BudgetSetup"))
<Route path="/welcome/budget" element={<RequireAuth><BudgetSetup /></RequireAuth>} />
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/onboarding/BudgetSetup.tsx frontend/src/App.tsx
git commit -m "feat(pivot): budget setup page with age + CGU confirm"
```

---

## Task 15: OrderForm refactor — slider + limits enforcement

**Files:**
- Modify: `frontend/src/components/signals/OrderForm.tsx`
- Test: `frontend/src/components/signals/__tests__/OrderForm.test.tsx`

- [ ] **Step 1: Écrire le test**

```tsx
// frontend/src/components/signals/__tests__/OrderForm.test.tsx
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { MOCK_SIGNALS } from "@/data/signals"
import { OrderForm } from "../OrderForm"

vi.mock("@/hooks/useUserLimits", () => ({
  useUserLimits: () => ({
    data: {
      budgetWeeklyEur: 20, maxStakeEur: 10, level: 1,
      realTradesCount: 0, consecutiveLosses: 0, weekSpentEur: 15,
      cooloffUntil: null, quizPassed: true, ageConfirmed18: true,
    },
    isLoading: false,
  }),
}))

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient()
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

describe("OrderForm — limits", () => {
  it("caps slider to maxStakeEur", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} onClose={() => {}} />))
    const slider = screen.getByRole("slider", { name: /mise/i }) as HTMLInputElement
    expect(slider.max).toBe("10")
  })

  it("shows remaining weekly budget", () => {
    render(wrap(<OrderForm signal={MOCK_SIGNALS[0]} onClose={() => {}} />))
    expect(screen.getByText(/reste 5€/i)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Run — doit échouer**

Run: `cd frontend && npm run test -- OrderForm.test.tsx`
Expected: FAIL — slider absent ou max différent.

- [ ] **Step 3: Refactorer OrderForm**

Dans `OrderForm.tsx`, remplacer l'input libre `amount` par un slider. Ajouter useUserLimits. En tête de fichier :

```tsx
import { useUserLimits } from "@/hooks/useUserLimits"
```

Dans le composant, remplacer la logique de montant par :

```tsx
const { data: limits, isLoading } = useUserLimits()
const maxStake = limits?.maxStakeEur ?? 10
const remaining = limits ? limits.budgetWeeklyEur - limits.weekSpentEur : 0
const inCooloff = limits?.cooloffUntil ? new Date(limits.cooloffUntil) > new Date() : false

const [amount, setAmount] = useState(Math.min(5, maxStake))
const effectiveMax = Math.max(1, Math.min(maxStake, remaining))

// ...dans le JSX, à la place de l'input amount :
{inCooloff ? (
  <div className="rounded-lg bg-signal-no/10 p-3 text-sm">
    Tu es en pause (cooloff). Reprise : {new Date(limits!.cooloffUntil!).toLocaleString("fr-FR")}
  </div>
) : (
  <>
    <label className="text-sm font-semibold" htmlFor="stake-slider">Mise (€)</label>
    <input
      id="stake-slider"
      type="range"
      aria-label="Mise"
      min={1}
      max={effectiveMax}
      step={1}
      value={amount}
      onChange={e => setAmount(Number(e.target.value))}
      className="w-full"
    />
    <p className="text-xl font-bold">{amount}€</p>
    <p className="text-xs text-muted-foreground">
      Max par trade : {maxStake}€ · reste {remaining}€ cette semaine
    </p>
  </>
)}
```

Désactiver le bouton "Placer l'ordre" si `inCooloff || amount > effectiveMax`.

- [ ] **Step 4: Run test**

Run: `cd frontend && npm run test -- OrderForm.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/signals/OrderForm.tsx frontend/src/components/signals/__tests__/OrderForm.test.tsx
git commit -m "feat(pivot): OrderForm uses slider + enforces user limits + cooloff"
```

---

## Task 16: BudgetBar sticky + CooloffModal

**Files:**
- Create: `frontend/src/components/layout/BudgetBar.tsx`
- Create: `frontend/src/components/modals/CooloffModal.tsx`
- Modify: `frontend/src/components/layout/AppShell.tsx`
- Test: `frontend/src/components/layout/__tests__/BudgetBar.test.tsx`

- [ ] **Step 1: Test de BudgetBar**

```tsx
// frontend/src/components/layout/__tests__/BudgetBar.test.tsx
import { render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { describe, expect, it, vi } from "vitest"
import { BudgetBar } from "../BudgetBar"

vi.mock("@/hooks/useUserLimits", () => ({
  useUserLimits: vi.fn(),
}))
import { useUserLimits } from "@/hooks/useUserLimits"

function wrap(ui: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>
}

describe("BudgetBar", () => {
  it("shows spent / budget", () => {
    ;(useUserLimits as any).mockReturnValue({
      data: { budgetWeeklyEur: 20, weekSpentEur: 12, cooloffUntil: null, ageConfirmed18: true, quizPassed: true },
      isLoading: false,
    })
    render(wrap(<BudgetBar />))
    expect(screen.getByText(/12€ \/ 20€/)).toBeInTheDocument()
  })

  it("returns null if no limits", () => {
    ;(useUserLimits as any).mockReturnValue({ data: undefined, isLoading: false })
    const { container } = render(wrap(<BudgetBar />))
    expect(container).toBeEmptyDOMElement()
  })
})
```

- [ ] **Step 2: Run — doit échouer**

Run: `cd frontend && npm run test -- BudgetBar.test.tsx`
Expected: FAIL — composant absent.

- [ ] **Step 3: Écrire BudgetBar**

```tsx
// frontend/src/components/layout/BudgetBar.tsx
import { useUserLimits } from "@/hooks/useUserLimits"

export function BudgetBar() {
  const { data } = useUserLimits()
  if (!data) return null
  const pct = Math.min(100, (data.weekSpentEur / data.budgetWeeklyEur) * 100)
  const inCooloff = data.cooloffUntil ? new Date(data.cooloffUntil) > new Date() : false

  return (
    <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-card/50">
      {inCooloff ? (
        <span className="text-xs text-signal-no font-semibold">⏸ En pause (cooloff actif)</span>
      ) : (
        <>
          <span className="text-xs text-muted-foreground">Cette semaine :</span>
          <span className="text-sm font-semibold">
            {data.weekSpentEur.toFixed(0)}€ / {data.budgetWeeklyEur.toFixed(0)}€
          </span>
          <div className="flex-1 h-2 rounded-full bg-obsidian-800 overflow-hidden">
            <div
              className="h-full bg-brand-500 transition-all"
              style={{ width: `${pct}%` }}
            />
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Écrire CooloffModal**

```tsx
// frontend/src/components/modals/CooloffModal.tsx
type Props = {
  cooloffUntil: string
  onClose: () => void
}

export function CooloffModal({ cooloffUntil, onClose }: Props) {
  const until = new Date(cooloffUntil)
  return (
    <div className="fixed inset-0 z-50 bg-obsidian-950/80 flex items-center justify-center p-4">
      <div className="bg-card rounded-xl p-6 max-w-md space-y-4">
        <h2 className="text-xl font-bold">Pause de 24h</h2>
        <p className="text-sm">
          Tu as perdu 3 trades d'affilée. Le trading réel est en pause jusqu'au{" "}
          <strong>{until.toLocaleString("fr-FR")}</strong>.
        </p>
        <p className="text-sm text-muted-foreground">
          Pendant ce temps, tu peux lire les analyses et simuler des trades en paper trading.
        </p>
        <button
          onClick={onClose}
          className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold"
        >
          J'ai compris
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Intégrer BudgetBar dans AppShell**

Dans `frontend/src/components/layout/AppShell.tsx`, importer `BudgetBar` et l'insérer juste après le header top :

```tsx
import { BudgetBar } from "./BudgetBar"
// ...dans le JSX, après le header principal :
<BudgetBar />
```

- [ ] **Step 6: Run test**

Run: `cd frontend && npm run test -- BudgetBar.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/layout/BudgetBar.tsx frontend/src/components/layout/AppShell.tsx frontend/src/components/modals/CooloffModal.tsx frontend/src/components/layout/__tests__/BudgetBar.test.tsx
git commit -m "feat(pivot): sticky BudgetBar in AppShell + CooloffModal"
```

---

## Task 17: SignalOutcome page

**Files:**
- Create: `frontend/src/pages/SignalOutcome.tsx`
- Create: `frontend/src/components/learn/OutcomeExplainer.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/types/signal.ts` (ajouter `outcome` field)
- Modify: `frontend/src/lib/apiSignals.ts` (hydrater outcome)

- [ ] **Step 1: Étendre le type `Signal`**

Dans `frontend/src/types/signal.ts`, ajouter :

```typescript
export type SignalOutcome = {
  directionCorrect: boolean | null
  finalPrice: number | null
  basePrice: number | null
  movePct: number | null
  learningPoint: string
}

// dans le type Signal :
export type Signal = {
  // ...champs existants
  outcome?: SignalOutcome | null
}
```

- [ ] **Step 2: Hydrater dans `apiSignals.ts`**

Dans la fonction d'hydratation, mapper `wire.outcome` :

```typescript
outcome: wire.outcome ? {
  directionCorrect: wire.outcome.directionCorrect,
  finalPrice: wire.outcome.finalPrice,
  basePrice: wire.outcome.basePrice,
  movePct: wire.outcome.movePct,
  learningPoint: wire.outcome.learningPoint,
} : null,
```

- [ ] **Step 3: Écrire OutcomeExplainer**

```tsx
// frontend/src/components/learn/OutcomeExplainer.tsx
import type { SignalOutcome } from "@/types/signal"

type Props = { outcome: SignalOutcome }

export function OutcomeExplainer({ outcome }: Props) {
  const ok = outcome.directionCorrect === true
  const notOk = outcome.directionCorrect === false
  return (
    <section className={`rounded-xl border border-border p-6 space-y-3 ${ok ? "bg-signal-yes/5" : notOk ? "bg-signal-no/5" : "bg-card"}`}>
      <div className="flex items-center gap-2">
        <span className="text-2xl">{ok ? "✓" : notOk ? "✗" : "—"}</span>
        <h3 className="text-lg font-semibold">
          {ok ? "Direction correcte" : notOk ? "Direction incorrecte" : "Résultat indéterminé"}
        </h3>
      </div>
      {outcome.basePrice !== null && outcome.finalPrice !== null && (
        <p className="text-sm">
          Prix au signal : <strong>{(outcome.basePrice * 100).toFixed(0)}%</strong> →{" "}
          résolution : <strong>{(outcome.finalPrice * 100).toFixed(0)}%</strong>
          {outcome.movePct !== null && (
            <> (mouvement : <strong>{outcome.movePct > 0 ? "+" : ""}{outcome.movePct.toFixed(1)}%</strong>)</>
          )}
        </p>
      )}
      <p className="text-sm leading-relaxed">{outcome.learningPoint}</p>
    </section>
  )
}
```

- [ ] **Step 4: Écrire la page SignalOutcome**

```tsx
// frontend/src/pages/SignalOutcome.tsx
import { useEffect } from "react"
import { useNavigate, useParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { apiPost } from "@/lib/api/client"
import { fetchSignalsFromApi } from "@/lib/apiSignals"
import { OutcomeExplainer } from "@/components/learn/OutcomeExplainer"
import { WhyThisMatters } from "@/components/signals/WhyThisMatters"
import { SourcesList } from "@/components/signals/SourcesList"

export default function SignalOutcome() {
  const { id = "" } = useParams()
  const navigate = useNavigate()

  const { data: signals = [] } = useQuery({
    queryKey: ["signal", id],
    queryFn: () => fetchSignalsFromApi(),
  })
  const signal = signals.find(s => s.id === id)

  useEffect(() => {
    if (signal?.outcome) {
      apiPost(`/signals/${id}/outcome/viewed`, {}).catch(() => {})
    }
  }, [id, signal?.outcome])

  if (!signal) return <div className="p-6">Chargement…</div>

  if (!signal.outcome) {
    return (
      <div className="p-6 mx-auto max-w-2xl space-y-4">
        <h1 className="text-2xl font-bold">{signal.question}</h1>
        <p className="text-sm text-muted-foreground">
          Ce signal n'est pas encore résolu. Reviens quand le marché aura tranché.
        </p>
        <button onClick={() => navigate(`/signals/${id}`)} className="underline">
          Retour au signal
        </button>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl p-6 space-y-6">
      <h1 className="text-2xl font-bold">{signal.question}</h1>
      <OutcomeExplainer outcome={signal.outcome} />
      <WhyThisMatters reasoning={signal.reasoning ?? null} sourceTierMix={null} />
      {signal.detailedSources && <SourcesList sources={signal.detailedSources} />}
      <button
        onClick={() => navigate("/signals")}
        className="w-full rounded-lg bg-brand-500 text-obsidian-950 py-3 font-semibold"
      >
        Compris, voir d'autres signaux
      </button>
    </div>
  )
}
```

- [ ] **Step 5: Route**

```tsx
const SignalOutcome = lazy(() => import("./pages/SignalOutcome"))
<Route path="/signals/:id/outcome" element={<RequireAuth><SignalOutcome /></RequireAuth>} />
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SignalOutcome.tsx frontend/src/components/learn/OutcomeExplainer.tsx frontend/src/App.tsx frontend/src/types/signal.ts frontend/src/lib/apiSignals.ts
git commit -m "feat(pivot): signal outcome explainer page"
```

---

## Task 18: Repositioning — landing hero + default route + UI copy

**Files:**
- Modify: `frontend/src/pages/Homepage.tsx`
- Modify: `frontend/src/pages/Welcome.tsx`
- Modify: `frontend/src/App.tsx` (default post-login route)
- Modify: `frontend/src/components/signals/SignalCard.tsx` (rename score label)
- Modify: `frontend/src/locales/fr/common.json`
- Modify: `frontend/src/locales/en/common.json`

- [ ] **Step 1: Changer le hero de Homepage**

Dans `frontend/src/pages/Homepage.tsx`, changer le hero principal pour :

```
Titre : "Apprends à trader les événements du monde avec 5€"
Sous-titre : "Chaque signal = un cas d'étude en temps réel. Paper trading gratuit pour t'entraîner. Trading réel quand tu es prêt."
CTA primaire : "Commencer gratuit"  → /signup
CTA secondaire : "Voir un exemple"  → /signal-variants
```

- [ ] **Step 2: Post-login par défaut = /signals si onboarding complet, sinon /welcome/tutorial**

Dans `App.tsx`, ajouter une logique de redirection post-login. Utiliser `useOnboardingStatus` :

```tsx
// Dans RequireOnboarding ou un nouveau guard :
const { data: status } = useOnboardingStatus()
if (status && !status.tutorialDone && location.pathname.startsWith("/signals")) {
  return <Navigate to="/welcome/tutorial" replace />
}
if (status && status.tutorialDone && !status.quizDone && location.pathname.startsWith("/signals")) {
  return <Navigate to="/welcome/quiz" replace />
}
if (status && status.tutorialDone && status.quizDone && !status.budgetDone && location.pathname.startsWith("/signals")) {
  return <Navigate to="/welcome/budget" replace />
}
```

- [ ] **Step 3: Rename score label dans SignalCard**

Dans `SignalCard.tsx`, remplacer le label `"Score"` par `"Catalyseur"` (ou clé i18n `signal.catalystStrength`). Le calcul backend ne change pas, seul le texte UI.

- [ ] **Step 4: i18n keys**

Dans `frontend/src/locales/fr/common.json`, ajouter :

```json
{
  "signal": {
    "catalystStrength": "Catalyseur",
    "watchOnPolymarket": "Voir sur Polymarket"
  },
  "onboarding": {
    "tutorialTitle": "Tutoriel — 5 scénarios",
    "quizTitle": "Quiz risque",
    "budgetTitle": "Définis tes limites"
  },
  "limits": {
    "weeklyBudget": "Budget hebdo",
    "maxStake": "Mise max",
    "cooloffActive": "Pause active"
  }
}
```

Même structure en placeholder (FR) dans `en/common.json`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Homepage.tsx frontend/src/pages/Welcome.tsx frontend/src/App.tsx frontend/src/components/signals/SignalCard.tsx frontend/src/locales/
git commit -m "feat(pivot): repositioning — learn-and-trade hero, catalyst label, redirect gates"
```

---

## Task 19: Gamification — XP, badges, streaks (éducatifs)

**Files:**
- Create: `frontend/src/components/gamification/XPBadge.tsx`
- Create: `frontend/src/components/gamification/StreakIndicator.tsx`
- Create: `frontend/src/lib/gamification.ts`
- Modify: `frontend/src/pages/Portfolio.tsx`

- [ ] **Step 1: Définir le calcul XP/badges côté client**

Créer `frontend/src/lib/gamification.ts` :

```typescript
import type { OnboardingStatus } from "@/lib/api/onboarding"
import type { PaperPosition } from "@/lib/api/paper"

export type Badge = {
  id: string
  label: string
  icon: string
  earned: boolean
}

export function computeXP(input: {
  outcomeViews: number
  paperTrades: number
  realTrades: number
  tutorialDone: boolean
  quizPassed: boolean
}): number {
  return (
    input.outcomeViews * 5 +
    input.paperTrades * 3 +
    input.realTrades * 2 +
    (input.tutorialDone ? 25 : 0) +
    (input.quizPassed ? 25 : 0)
  )
}

export function computeLevel(xp: number): number {
  return 1 + Math.floor(Math.sqrt(xp / 50))
}

export function computeBadges(input: {
  outcomeViews: number
  paperTrades: number
  tutorialDone: boolean
  quizPassed: boolean
}): Badge[] {
  return [
    { id: "tutorial", label: "Tutoriel terminé", icon: "🎓", earned: input.tutorialDone },
    { id: "quiz", label: "Quiz risque validé", icon: "🧠", earned: input.quizPassed },
    { id: "first-paper", label: "Premier paper trade", icon: "📝", earned: input.paperTrades >= 1 },
    { id: "ten-outcomes", label: "10 outcomes lus", icon: "📖", earned: input.outcomeViews >= 10 },
    { id: "fifty-papers", label: "50 paper trades", icon: "🏆", earned: input.paperTrades >= 50 },
  ]
}

export function computeStreak(viewedDates: string[]): number {
  if (viewedDates.length === 0) return 0
  const days = new Set(viewedDates.map(d => d.slice(0, 10)))
  let streak = 0
  const cursor = new Date()
  cursor.setHours(0, 0, 0, 0)
  for (let i = 0; i < 365; i++) {
    const key = cursor.toISOString().slice(0, 10)
    if (days.has(key)) {
      streak += 1
      cursor.setDate(cursor.getDate() - 1)
    } else {
      break
    }
  }
  return streak
}
```

- [ ] **Step 2: Écrire XPBadge + StreakIndicator**

```tsx
// frontend/src/components/gamification/XPBadge.tsx
type Props = { xp: number; level: number }

export function XPBadge({ xp, level }: Props) {
  return (
    <div className="flex items-center gap-2 rounded-full bg-brand-500/10 px-3 py-1 text-xs">
      <span aria-hidden>⭐</span>
      <span className="font-semibold">Niv. {level}</span>
      <span className="text-muted-foreground">· {xp} XP</span>
    </div>
  )
}
```

```tsx
// frontend/src/components/gamification/StreakIndicator.tsx
type Props = { days: number }

export function StreakIndicator({ days }: Props) {
  if (days === 0) return null
  return (
    <div className="flex items-center gap-1 text-xs">
      <span aria-hidden>🔥</span>
      <span className="font-semibold">{days} jour{days > 1 ? "s" : ""}</span>
    </div>
  )
}
```

- [ ] **Step 3: Intégrer dans Portfolio.tsx**

Dans `Portfolio.tsx`, importer `computeXP`, `computeLevel`, `computeBadges`, `XPBadge` et afficher :

```tsx
import { XPBadge } from "@/components/gamification/XPBadge"
import { computeXP, computeLevel, computeBadges } from "@/lib/gamification"
import { useOnboardingStatus } from "@/hooks/useOnboarding"
import { usePaperPortfolio } from "@/hooks/usePaperPortfolio"

// dans le composant :
const { data: onb } = useOnboardingStatus()
const { data: paperPositions = [] } = usePaperPortfolio()
const xp = computeXP({
  outcomeViews: 0,  // brancher si endpoint disponible
  paperTrades: paperPositions.length,
  realTrades: 0,  // brancher via portfolio réel
  tutorialDone: !!onb?.tutorialDone,
  quizPassed: !!onb?.quizDone,
})
const level = computeLevel(xp)
const badges = computeBadges({
  outcomeViews: 0,
  paperTrades: paperPositions.length,
  tutorialDone: !!onb?.tutorialDone,
  quizPassed: !!onb?.quizDone,
})

// dans le JSX header :
<XPBadge xp={xp} level={level} />

// section badges :
<section className="rounded-xl border border-border p-4">
  <h3 className="text-sm font-semibold uppercase text-muted-foreground mb-3">Badges</h3>
  <div className="flex flex-wrap gap-2">
    {badges.map(b => (
      <div
        key={b.id}
        className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs ${
          b.earned ? "bg-signal-yes/10 text-signal-yes" : "bg-obsidian-800 text-muted-foreground opacity-50"
        }`}
      >
        <span>{b.icon}</span>
        <span>{b.label}</span>
      </div>
    ))}
  </div>
</section>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/gamification/ frontend/src/lib/gamification.ts frontend/src/pages/Portfolio.tsx
git commit -m "feat(pivot): educational gamification (XP, badges, streaks)"
```

---

## Task 20: Pricing page — Free vs Pro tiers

**Files:**
- Modify: `frontend/src/pages/Pricing.tsx`

- [ ] **Step 1: Réécrire le contenu des tiers**

Remplacer les tiers actuels par :

```tsx
const TIERS = [
  {
    name: "Free",
    priceMonthly: 0,
    priceYearly: 0,
    features: [
      "Paper trading illimité",
      "Tutoriel + quiz",
      "Feed signaux (10/jour)",
      "Outcome explainer après résolution",
      "Budget hebdo max : 20€ réel",
      "Max stake : 5€",
    ],
    cta: "Commencer gratuit",
    href: "/signup",
  },
  {
    name: "Pro",
    priceMonthly: 9,
    priceYearly: 79,
    features: [
      "Tout le Free",
      "Feed illimité",
      "Analytics avancés (winrate, baselines, edges)",
      "Alertes push temps réel",
      "Budget hebdo max : 200€ réel",
      "Max stake : 50€",
      "Historique paper + réel exportable CSV",
    ],
    cta: "Passer Pro",
    href: "/signup?plan=pro",
    highlight: true,
  },
]
```

Adapter le rendu en conséquence (garder la structure existante du composant, remplacer juste les données + copy).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Pricing.tsx
git commit -m "feat(pivot): pricing tiers Free vs Pro with paper+real caps"
```

---

## Task 21: CGU + mentions légales + disclaimers (pages statiques)

**Files:**
- Create: `frontend/src/pages/Cgu.tsx`
- Create: `frontend/src/pages/Risques.tsx`
- Create: `frontend/src/pages/MentionsLegales.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Écrire les 3 pages en placeholder signé**

Chaque page est un markdown rendu dans un layout public. Exemple :

```tsx
// frontend/src/pages/Risques.tsx
import { Footer } from "@/components/layout/Footer"
import { PublicNav } from "@/components/layout/PublicNav"

export default function Risques() {
  return (
    <div className="min-h-screen bg-obsidian-950 text-ink-default">
      <PublicNav />
      <main className="mx-auto max-w-2xl px-6 py-16 space-y-6">
        <h1 className="text-3xl font-bold">Politique de risque</h1>
        <p>
          Les marchés prédictifs sont un produit à haut risque. Tu peux perdre la
          totalité de la mise que tu engages. Avant tout trade réel :
        </p>
        <ul className="list-disc pl-6 space-y-2">
          <li>Ne trade jamais plus que ce que tu peux te permettre de perdre.</li>
          <li>Les signaux sont une analyse d'intérêt éducative, pas une recommandation d'investissement.</li>
          <li>Le passé ne garantit pas l'avenir. Un winrate historique peut s'inverser.</li>
          <li>Tu restes seul responsable de tes décisions d'investissement.</li>
          <li>Si tu te sens dépassé, utilise le cooloff ou contacte Joueurs Info Service (09 74 75 13 13).</li>
        </ul>
        <p className="text-sm text-muted-foreground">
          Ce site ne fournit pas de conseil en investissement au sens de l'AMF. L'accès à Polymarket peut être restreint dans certaines juridictions ; tu es responsable de vérifier la légalité d'usage dans ton pays de résidence.
        </p>
      </main>
      <Footer />
    </div>
  )
}
```

Même pattern pour `Cgu.tsx` (texte CGU placeholder à faire valider par avocat) et `MentionsLegales.tsx` (éditeur, hébergeur, contact).

**Important** : ces textes sont des placeholders initiaux. Les valider avec un avocat fintech FR avant mise en prod publique.

- [ ] **Step 2: Routes publiques**

```tsx
const Cgu = lazy(() => import("./pages/Cgu"))
const Risques = lazy(() => import("./pages/Risques"))
const MentionsLegales = lazy(() => import("./pages/MentionsLegales"))
<Route path="/cgu" element={<Cgu />} />
<Route path="/risques" element={<Risques />} />
<Route path="/mentions-legales" element={<MentionsLegales />} />
```

- [ ] **Step 3: Footer links**

Dans `frontend/src/components/layout/Footer.tsx`, ajouter des liens vers `/cgu`, `/risques`, `/mentions-legales`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Cgu.tsx frontend/src/pages/Risques.tsx frontend/src/pages/MentionsLegales.tsx frontend/src/App.tsx frontend/src/components/layout/Footer.tsx
git commit -m "feat(pivot): add CGU, risk policy, mentions légales placeholder pages"
```

---

## Task 22: Data migration pour users existants

**Files:**
- Create: `scripts/backfill_user_limits.py`
- Test: `tests/unit/test_backfill_user_limits.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_backfill_user_limits.py
from __future__ import annotations
import pytest
from app.db.database import get_session_factory
from app.db.models import UserLimits, UserProfile
from scripts.backfill_user_limits import backfill


@pytest.mark.asyncio
async def test_backfill_creates_rows_for_users_without_limits():
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserProfile(id=700001, email="a@test.fr", plan="free"))
        s.add(UserProfile(id=700002, email="b@test.fr", plan="pro"))
        await s.commit()

    created = await backfill(dry_run=False)
    assert created >= 2

    async with factory() as s:
        row_a = await s.get(UserLimits, 700001)
        row_b = await s.get(UserLimits, 700002)
    assert row_a is not None
    assert row_b is not None
    assert float(row_a.budget_weekly_eur) == 20.00
    assert row_a.quiz_passed is False  # force re-quiz
    assert row_a.age_confirmed_18 is False  # force re-confirm
```

- [ ] **Step 2: Écrire le script**

```python
# scripts/backfill_user_limits.py
"""Create UserLimits + OnboardingProgress rows for existing users.

Users must re-confirm age, accept new CGU, and pass quiz before next real trade.
"""

from __future__ import annotations
import argparse
import asyncio
import logging
from sqlalchemy import select

from app.db.database import get_session_factory
from app.db.models import OnboardingProgress, UserLimits, UserProfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def backfill(dry_run: bool) -> int:
    factory = get_session_factory()
    async with factory() as s:
        users = (await s.execute(select(UserProfile.id))).scalars().all()
        existing_limits = (
            await s.execute(select(UserLimits.user_id))
        ).scalars().all()
        existing_onb = (
            await s.execute(select(OnboardingProgress.user_id))
        ).scalars().all()

    to_create = set(users) - set(existing_limits)
    to_create_onb = set(users) - set(existing_onb)
    logger.info("backfill: users=%d missing_limits=%d missing_onb=%d dry=%s",
                len(users), len(to_create), len(to_create_onb), dry_run)

    if dry_run:
        return 0

    async with factory() as s:
        for uid in to_create:
            s.add(UserLimits(
                user_id=uid,
                budget_weekly_eur=20.00,
                max_stake_eur=10.00,
                quiz_passed=False,
                age_confirmed_18=False,
            ))
        for uid in to_create_onb:
            s.add(OnboardingProgress(user_id=uid))
        await s.commit()

    return len(to_create)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.dry_run))
```

- [ ] **Step 3: Run test**

Run: `docker compose exec app pytest tests/unit/test_backfill_user_limits.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/backfill_user_limits.py tests/unit/test_backfill_user_limits.py
git commit -m "feat(pivot): backfill script for existing users' limits + onboarding"
```

---

## Task 23: Route `/me/limits` pour UserLimits + intégration frontend

**Files:**
- Modify: `app/api/routes/auth.py` (ou nouveau module limits)
- Test: `tests/unit/test_me_limits.py`

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/test_me_limits.py
from __future__ import annotations
import pytest
from httpx import AsyncClient
from app.api.main import app
from app.db.database import get_session_factory
from app.db.models import UserLimits


@pytest.mark.asyncio
async def test_get_me_limits(auth_headers_for_user):
    uid, headers = await auth_headers_for_user()
    factory = get_session_factory()
    async with factory() as s:
        s.add(UserLimits(
            user_id=uid, budget_weekly_eur=50, max_stake_eur=10,
            quiz_passed=True, age_confirmed_18=True, week_spent_eur=12,
        ))
        await s.commit()

    async with AsyncClient(app=app, base_url="http://t") as c:
        r = await c.get("/api/me/limits", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["budget_weekly_eur"] == 50
    assert data["max_stake_eur"] == 10
    assert data["week_spent_eur"] == 12
```

- [ ] **Step 2: Ajouter la route dans `app/api/routes/quota.py`** (qui a déjà prefix `/me`)

```python
from app.api.schemas.learn_and_trade import UserLimitsOut
from app.db.models import UserLimits

@router.get("/limits", response_model=UserLimitsOut)
async def get_my_limits(
    user: UserProfile = Depends(get_current_user),
) -> UserLimitsOut:
    factory = get_session_factory()
    async with factory() as s:
        limits = await s.get(UserLimits, user.id)
    if limits is None:
        # return safe defaults
        return UserLimitsOut(
            budget_weekly_eur=20.00, max_stake_eur=10.00, level=1,
            real_trades_count=0, consecutive_losses=0, week_spent_eur=0.00,
            cooloff_until=None, quiz_passed=False, age_confirmed_18=False,
        )
    return UserLimitsOut.model_validate(limits, from_attributes=True)
```

- [ ] **Step 3: Run test**

Run: `docker compose exec app pytest tests/unit/test_me_limits.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add app/api/routes/quota.py tests/unit/test_me_limits.py
git commit -m "feat(pivot): GET /api/me/limits for frontend"
```

---

## Task 24: Vérif finale + merge

- [ ] **Step 1: Lint + tests complets**

```bash
# Backend
docker compose exec app make lint && docker compose exec app make test

# Frontend
cd frontend && npm run lint && npm run test
```

Expected: tout vert.

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: pas d'erreur TS, bundle produit dans `dist/`.

- [ ] **Step 3: Smoke test manuel**

Lancer la stack complète :

```bash
docker compose up -d
```

Scénario à valider manuellement :
1. `GET http://localhost:3000/` → hero "Apprends à trader…"
2. Signup sans age 18+ coché → bouton disabled
3. Signup avec age + CGU → redirige vers `/welcome` puis `/welcome/tutorial`
4. Faire 5 scénarios → redirige vers `/welcome/quiz`
5. Faire le quiz 3/3 → redirige vers `/welcome/budget`
6. Définir budget + accepter → redirige vers `/signals`
7. Ouvrir un signal → `OrderForm` avec slider capé
8. Vérifier `BudgetBar` en haut avec pct
9. `POST /api/trading/trade` depuis curl sans quiz passé → 403 `quiz_not_passed`

- [ ] **Step 4: Merge**

```bash
git checkout main
git merge --no-ff pivot/learn-and-trade
git push origin main
```

Ne **pas** déployer en prod sans :
- Audit légal CGU / politique risque validé
- Backfill scripts exécutés (`scripts/backfill_user_limits.py`)
- Documentation utilisateur mise à jour

---

## Post-plan — ce qui N'EST PAS dans ce plan (hors scope)

- **Audit mesures** (5 chantiers `audit/measurement-fixes`) — plan séparé, tourne en parallèle
- **Refonte scoring** — gelé jusqu'à J+10 minimum
- **Abstraction LLM provider** — ticket séparé
- **Scaling WebSocket / Celery** — non-critique
- **KYC / vérification identité** — à évaluer après audit légal
- **Push notifications** — mentionné dans Pro tier mais reporté
- **Leaderboards community** — reporté post-MVP
- **Abstraction Telegram bot pour alertes** — reporté

---

**Plan complete.** 24 tâches, ~2-3 semaines de dev pour un engineer full-time.
