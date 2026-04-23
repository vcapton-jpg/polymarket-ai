"""Admin gate.

`require_admin` is a FastAPI dependency that rejects non-admin callers with
403. Admins are identified by the `ADMIN_EMAILS` env var — a comma-separated
allowlist. This is intentionally low-tech: we have no role column yet, and
adding one for a single permission tier is YAGNI. Migrate to a role table
if/when we grow a second tier.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.models import UserProfile


def _parse_admin_emails(raw: str) -> set[str]:
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def _is_admin_email(email: str | None, raw_list: str) -> bool:
    if not email:
        return False
    return email.strip().lower() in _parse_admin_emails(raw_list)


async def require_admin(
    user: UserProfile = Depends(get_current_user),
) -> UserProfile:
    settings = get_settings()
    if not _is_admin_email(user.email, settings.admin_emails):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
