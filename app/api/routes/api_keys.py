"""B2B API key management routes.

Auth model (post-2026-04-27 audit fix):
- `create` : `require_admin` — issuing a B2B key is a privileged op (the
  key bypasses the per-IP rate limit and unlocks the public B2B feed).
  Pre-fix this endpoint accepted unauthenticated requests, letting any
  caller mint themselves a 10 000 req/min `enterprise` key.
- `list`   : `require_admin` — exposes every key's prefix + tier across
  all users. Same threat model as `create`.
- `revoke` : `require_admin` — revoking a key affects another user's
  access. Admin-only is correct.

For per-user self-service of their OWN keys, add a separate `/me/api-keys`
namespace later (out of scope for the security patch).
"""

import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.admin import require_admin
from app.db.database import get_db_session
from app.db.models import ApiKeyB2B, UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    tier: str = "basic"


class ApiKeyOut(BaseModel):
    id: int
    key_prefix: str
    tier: str
    rate_limit: int
    active: bool
    created_at: str


class ApiKeyCreated(BaseModel):
    key: str
    key_prefix: str
    tier: str
    rate_limit: int


@router.post("/create", response_model=ApiKeyCreated)
async def create_api_key(
    req: CreateKeyRequest,
    admin: UserProfile = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new B2B API key (admin-only).

    The key is associated with the calling admin's user_id. The plaintext
    key is returned exactly once in the response and is not retrievable
    later — the DB only stores its sha256 hash.
    """
    raw_key = f"sig_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:12]

    rate_limits = {"basic": 100, "pro": 1000, "enterprise": 10000}
    rate_limit = rate_limits.get(req.tier, 100)

    api_key = ApiKeyB2B(
        user_id=admin.id,
        key_hash=key_hash,
        key_prefix=prefix,
        tier=req.tier,
        rate_limit=rate_limit,
    )
    db.add(api_key)
    await db.commit()

    logger.info(
        "B2B API key issued: prefix=%s tier=%s rate_limit=%d issued_by_user_id=%s",
        prefix, req.tier, rate_limit, admin.id,
    )

    return ApiKeyCreated(
        key=raw_key,
        key_prefix=prefix,
        tier=req.tier,
        rate_limit=rate_limit,
    )


@router.get("/", response_model=list[ApiKeyOut])
async def list_api_keys(
    admin: UserProfile = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """List all API keys (admin-only)."""
    result = await db.execute(
        select(ApiKeyB2B).order_by(ApiKeyB2B.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyOut(
            id=k.id,
            key_prefix=k.key_prefix,
            tier=k.tier,
            rate_limit=k.rate_limit,
            active=k.active,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: int,
    admin: UserProfile = Depends(require_admin),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke an API key (admin-only)."""
    result = await db.execute(select(ApiKeyB2B).where(ApiKeyB2B.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    key.active = False
    await db.commit()
    logger.info("B2B API key revoked: prefix=%s revoked_by_user_id=%s", key.key_prefix, admin.id)
    return {"status": "revoked"}
