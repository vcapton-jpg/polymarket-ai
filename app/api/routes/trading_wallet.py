"""Wallet connection endpoints — EOA registration + Safe deployment.

Auth flow (post-2026-04-27 P0-3 audit fix):
1. Frontend asks `GET /api/trading/wallet/nonce` — backend returns a
   freshly-generated random nonce and stores `wallet_nonce:{user_id}`
   in Redis with a 5-minute TTL. The response also returns the exact
   message template the user must sign.
2. Frontend asks the user's wallet (wagmi/MetaMask) to sign that
   message via `personal_sign`.
3. Frontend posts `{eoa_address, nonce, signature}` to
   `POST /api/trading/wallet/connect`. Backend verifies:
   - the nonce matches the stored Redis value (one-shot)
   - the signature recovers to the supplied EOA via `eth_account`
   Only then does it pay gas + deploy a Safe.

Pre-fix the connect endpoint accepted `eoa_address` only — meaning
any authenticated user could submit arbitrary EOAs (1000 different
addresses → 1000 Safe deployments × $0.001 gas each = builder wallet
drain). The signature challenge proves the caller controls the
private key for the supplied EOA before any gas is paid.
"""

import logging
import secrets

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from web3 import Web3

from app.api.routes.auth import get_current_user
from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import UserProfile
from app.trading.safe_deployer import SafeDeployer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading/wallet", tags=["trading-wallet"])

_deployer = SafeDeployer()

# Nonce TTL: 5 minutes. Long enough for a slow human + wallet UX, short
# enough that a stolen nonce expires before it's useful.
_NONCE_TTL_SECONDS = 300


def _nonce_key(user_id: int) -> str:
    return f"wallet_nonce:{user_id}"


def _build_signing_message(user_id: int, nonce: str) -> str:
    """Single source of truth for the message text both frontend and
    backend agree on. Any drift between the two breaks signature
    verification — keep this function the only producer.
    """
    return (
        "Foresight wallet linking\n"
        f"Account: {user_id}\n"
        f"Nonce: {nonce}\n"
        "By signing, you authorize Foresight to deploy a Polymarket "
        "Safe owned by your EOA."
    )


async def _get_redis():
    """Local async Redis client. Inlined (rather than importing the
    quota module's helper) to keep this route file's deps explicit.
    """
    import redis.asyncio as aioredis

    settings = get_settings()
    return aioredis.from_url(settings.redis_url, decode_responses=True)


class NonceResponse(BaseModel):
    nonce: str
    message: str
    expires_in_seconds: int


class ConnectRequest(BaseModel):
    eoa_address: str
    nonce: str
    signature: str


class WalletStatusResponse(BaseModel):
    connected: bool
    eoa_address: str | None
    safe_address: str | None


class ConnectResponse(BaseModel):
    safe_address: str


@router.get("/status", response_model=WalletStatusResponse)
async def wallet_status(
    user: UserProfile = Depends(get_current_user),
):
    return WalletStatusResponse(
        connected=bool(user.polymarket_safe_address),
        eoa_address=user.wallet_address,
        safe_address=user.polymarket_safe_address,
    )


@router.get("/nonce", response_model=NonceResponse)
async def wallet_nonce(
    user: UserProfile = Depends(get_current_user),
):
    """Issue a one-shot nonce the user must sign with their EOA.

    Stores `{user_id: nonce}` in Redis with a 5-minute TTL. The
    response includes the exact message template the user must sign —
    using anything else will fail signature verification.
    """
    nonce = secrets.token_hex(16)
    message = _build_signing_message(user.id, nonce)

    r = await _get_redis()
    try:
        await r.set(_nonce_key(user.id), nonce, ex=_NONCE_TTL_SECONDS)
    finally:
        await r.aclose()

    return NonceResponse(
        nonce=nonce,
        message=message,
        expires_in_seconds=_NONCE_TTL_SECONDS,
    )


@router.post("/connect", response_model=ConnectResponse)
async def connect_wallet(
    body: ConnectRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Verify the user controls `eoa_address`, then deploy a Safe.

    The signature must be over the exact message returned by
    `/wallet/nonce` for this user. Pre-fix this endpoint accepted any
    EOA without proof of control — exposing the builder wallet's MATIC
    to a sustained drain attack.
    """
    try:
        eoa = Web3.to_checksum_address(body.eoa_address.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid EOA address") from exc

    if user.polymarket_safe_address:
        return ConnectResponse(safe_address=user.polymarket_safe_address)

    # 1. Verify the nonce matches what we stored for this user (one-shot).
    r = await _get_redis()
    try:
        stored = await r.get(_nonce_key(user.id))
        if stored is None:
            raise HTTPException(
                status_code=400,
                detail="Nonce expired or missing. Request a fresh one via /wallet/nonce.",
            )
        if stored != body.nonce:
            raise HTTPException(status_code=400, detail="Nonce mismatch.")
        # Consume the nonce on first use — prevents replay.
        await r.delete(_nonce_key(user.id))
    finally:
        await r.aclose()

    # 2. Verify the signature recovers to the supplied EOA.
    expected_message = _build_signing_message(user.id, body.nonce)
    try:
        recovered = Account.recover_message(
            encode_defunct(text=expected_message),
            signature=body.signature,
        )
    except Exception as exc:
        logger.warning(
            "wallet/connect signature recovery failed user_id=%s eoa=%s: %s",
            user.id, eoa, exc,
        )
        raise HTTPException(status_code=400, detail="Invalid signature.") from exc

    if Web3.to_checksum_address(recovered) != eoa:
        logger.warning(
            "wallet/connect signature recovers to %s but caller supplied %s (user_id=%s)",
            recovered, eoa, user.id,
        )
        raise HTTPException(
            status_code=400,
            detail="Signature does not match the supplied EOA.",
        )

    # 3. Only now deploy the Safe.
    try:
        safe_address = await _deployer.deploy_safe(eoa)
    except Exception as exc:
        logger.exception("Safe deployment failed for %s", eoa)
        raise HTTPException(
            status_code=500,
            detail="Safe deployment failed. Please try again or contact support.",
        ) from exc

    user.wallet_address = eoa
    user.polymarket_safe_address = safe_address
    await db.commit()

    logger.info(
        "Wallet connected: user_id=%s eoa=%s safe=%s",
        user.id, eoa, safe_address,
    )
    return ConnectResponse(safe_address=safe_address)
