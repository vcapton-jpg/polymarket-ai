"""One-off: create UserLimits + OnboardingProgress rows for pre-pivot users.

Existing users (pre-Learn-and-Trade) have no row in `user_limits` or
`onboarding_progress`. Since the pivot makes these authoritative gates
for any real-money order, we backfill them with safe defaults and
force a re-quiz + re-age-confirmation before the next real trade.

Defaults (intentionally conservative):
  - budget_weekly_eur = 20.00
  - max_stake_eur     = 10.00
  - quiz_passed       = False  (force re-quiz)
  - age_confirmed_18  = False  (force re-confirm)
  - OnboardingProgress: all flags default to False

The OrderForm + /me/limits both treat missing rows as "not
unlocked," so the gates stay closed until the user completes the
pivot onboarding flow.

Usage:
    docker compose exec app python -m scripts.backfill_user_limits --dry-run
    docker compose exec app python -m scripts.backfill_user_limits
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
    """Return the number of `user_limits` rows newly created (0 on dry-run)."""
    factory = get_session_factory()
    async with factory() as s:
        users = set((await s.execute(select(UserProfile.id))).scalars().all())
        existing_limits = set(
            (await s.execute(select(UserLimits.user_id))).scalars().all()
        )
        existing_onb = set(
            (await s.execute(select(OnboardingProgress.user_id))).scalars().all()
        )

    to_create_limits = users - existing_limits
    to_create_onb = users - existing_onb
    logger.info(
        "backfill: users=%d missing_limits=%d missing_onb=%d dry=%s",
        len(users),
        len(to_create_limits),
        len(to_create_onb),
        dry_run,
    )

    if dry_run:
        return 0

    async with factory() as s:
        for uid in to_create_limits:
            s.add(
                UserLimits(
                    user_id=uid,
                    budget_weekly_eur=20.00,
                    max_stake_eur=10.00,
                    quiz_passed=False,
                    age_confirmed_18=False,
                )
            )
        for uid in to_create_onb:
            s.add(OnboardingProgress(user_id=uid))
        await s.commit()

    logger.info(
        "backfill: committed limits=%d onboarding=%d",
        len(to_create_limits),
        len(to_create_onb),
    )
    return len(to_create_limits)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(backfill(args.dry_run))
