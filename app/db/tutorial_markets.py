"""Idempotent seeder for tutorial Market rows used by the Learn & Trade onboarding.

``paper_positions.market_id`` has a FK to ``markets.market_id`` with
``ondelete=CASCADE``. The 5 tutorial scenarios in
``frontend/src/content/tutorialScenarios.ts`` reference synthetic market_ids
(``tutorial_1`` … ``tutorial_5``). Those rows don't exist in Polymarket and
won't be produced by the ingestion workers, so we seed them on app startup.

The seeder is idempotent (``ON CONFLICT DO NOTHING``) — safe to call on every
boot. The rows are marked ``active=False`` so the ingestion/ranking workers
never touch them, and they don't appear in signal feeds.
"""

from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import Market

logger = logging.getLogger(__name__)


# Keep this list in sync with `frontend/src/content/tutorialScenarios.ts`.
# Only `market_id` + `question` are strictly needed; the rest of the Market
# columns are either nullable or have defaults.
_TUTORIAL_MARKETS: list[dict[str, str | bool]] = [
    {
        "market_id": "tutorial_1",
        "question": "L'équipe X va-t-elle gagner le championnat ?",
        "active": False,
    },
    {
        "market_id": "tutorial_2",
        "question": "Le gouvernement Y va-t-il passer la loi avant fin d'année ?",
        "active": False,
    },
    {
        "market_id": "tutorial_3",
        "question": "Le prix du bitcoin dépassera-t-il 100k$ ce mois ?",
        "active": False,
    },
    {
        "market_id": "tutorial_4",
        "question": "Le taux directeur de la BCE va-t-il baisser en juin ?",
        "active": False,
    },
    {
        "market_id": "tutorial_5",
        "question": "Le pays Z va-t-il ratifier l'accord climat avant la COP ?",
        "active": False,
    },
]


async def seed_tutorial_markets(engine: AsyncEngine) -> None:
    """Insert the 5 tutorial Market rows if missing.

    Uses PostgreSQL ``INSERT ... ON CONFLICT DO NOTHING`` keyed on
    ``market_id`` (primary key) so repeated boots are no-ops.
    """
    stmt = pg_insert(Market).values(_TUTORIAL_MARKETS).on_conflict_do_nothing(
        index_elements=["market_id"]
    )
    async with engine.begin() as conn:
        await conn.execute(stmt)
    logger.info("Tutorial markets ensured (%d rows)", len(_TUTORIAL_MARKETS))
