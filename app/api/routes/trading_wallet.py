"""Wallet connection endpoints — EOA registration + Safe deployment."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.db.database import get_db_session
from app.db.models import UserProfile
from app.trading.safe_deployer import SafeDeployer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trading/wallet", tags=["trading-wallet"])

_deployer = SafeDeployer()


class ConnectRequest(BaseModel):
    eoa_address: str


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


@router.post("/connect", response_model=ConnectResponse)
async def connect_wallet(
    body: ConnectRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    from web3 import Web3
    try:
        eoa = Web3.to_checksum_address(body.eoa_address.strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid EOA address")

    if user.polymarket_safe_address:
        return ConnectResponse(safe_address=user.polymarket_safe_address)

    try:
        safe_address = await _deployer.deploy_safe(eoa)
    except Exception:
        logger.exception("Safe deployment failed for %s", eoa)
        raise HTTPException(
            status_code=500,
            detail="Safe deployment failed. Please try again or contact support.",
        )

    user.wallet_address = eoa
    user.polymarket_safe_address = safe_address
    await db.commit()

    logger.info("Wallet connected: user=%s eoa=%s safe=%s", user.id, eoa, safe_address)
    return ConnectResponse(safe_address=safe_address)
