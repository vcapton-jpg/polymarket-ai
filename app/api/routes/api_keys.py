"""B2B API key management routes."""

import hashlib
import secrets
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
    db: AsyncSession = Depends(get_db_session),
):
    """Create a new B2B API key."""
    result = await db.execute(select(UserProfile).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        user = UserProfile(plan="free")
        db.add(user)
        await db.flush()

    raw_key = f"sig_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    prefix = raw_key[:12]

    rate_limits = {"basic": 100, "pro": 1000, "enterprise": 10000}
    rate_limit = rate_limits.get(req.tier, 100)

    api_key = ApiKeyB2B(
        user_id=user.id,
        key_hash=key_hash,
        key_prefix=prefix,
        tier=req.tier,
        rate_limit=rate_limit,
    )
    db.add(api_key)
    await db.commit()

    return ApiKeyCreated(
        key=raw_key,
        key_prefix=prefix,
        tier=req.tier,
        rate_limit=rate_limit,
    )


@router.get("/", response_model=list[ApiKeyOut])
async def list_api_keys(db: AsyncSession = Depends(get_db_session)):
    """List all API keys."""
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
async def revoke_api_key(key_id: int, db: AsyncSession = Depends(get_db_session)):
    """Revoke an API key."""
    result = await db.execute(select(ApiKeyB2B).where(ApiKeyB2B.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    key.active = False
    await db.commit()
    return {"status": "revoked"}
