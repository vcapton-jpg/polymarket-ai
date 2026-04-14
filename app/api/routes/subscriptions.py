"""Subscription management routes — Stripe integration."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session
from app.db.models import UserProfile

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


PLANS = {
    "free": {
        "name": "Free",
        "price": 0,
        "signals_per_day": 5,
        "execution": False,
        "risk_alerts": False,
        "daily_briefs": False,
        "api_access": False,
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "signals_per_day": -1,
        "execution": True,
        "risk_alerts": True,
        "daily_briefs": True,
        "api_access": False,
    },
    "enterprise": {
        "name": "Enterprise",
        "price": 199,
        "signals_per_day": -1,
        "execution": True,
        "risk_alerts": True,
        "daily_briefs": True,
        "api_access": True,
    },
}


class PlanInfo(BaseModel):
    name: str
    price: int
    signals_per_day: int
    execution: bool
    risk_alerts: bool
    daily_briefs: bool
    api_access: bool


@router.get("/plans")
async def get_plans():
    """Get available subscription plans."""
    return {"plans": PLANS}


@router.get("/current")
async def get_current_plan(db: AsyncSession = Depends(get_db_session)):
    """Get the current user's plan."""
    result = await db.execute(select(UserProfile).limit(1))
    user = result.scalar_one_or_none()
    plan = user.plan if user else "free"
    return {
        "plan": plan,
        "details": PLANS.get(plan, PLANS["free"]),
    }


@router.post("/checkout")
async def create_checkout(
    plan: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a Stripe checkout session."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    if plan not in ("pro", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    price_id = settings.stripe_price_pro if plan == "pro" else settings.stripe_price_enterprise
    if not price_id:
        raise HTTPException(status_code=503, detail="Stripe price not configured")

    result = await db.execute(select(UserProfile).limit(1))
    user = result.scalar_one_or_none()
    if not user:
        user = UserProfile(plan="free")
        db.add(user)
        await db.flush()
        await db.commit()

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url="https://signal.app/settings?checkout=success",
        cancel_url="https://signal.app/pricing",
        metadata={"user_id": str(user.id), "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db_session)):
    """Handle Stripe webhooks."""
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook not configured")

    import stripe
    stripe.api_key = settings.stripe_secret_key
    payload = await request.body()
    sig = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = int(session["metadata"]["user_id"])
        plan = session["metadata"]["plan"]
        result = await db.execute(select(UserProfile).where(UserProfile.id == user_id))
        user = result.scalar_one_or_none()
        if user:
            user.plan = plan
            user.stripe_customer_id = session.get("customer")
            await db.commit()
            logger.info("User %d upgraded to %s", user_id, plan)

    elif event["type"] == "customer.subscription.deleted":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        if customer_id:
            result = await db.execute(
                select(UserProfile).where(UserProfile.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            if user:
                user.plan = "free"
                await db.commit()

    return {"status": "ok"}
