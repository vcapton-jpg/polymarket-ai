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
from app.api.routes.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


PLANS = {
    "free": {
        "name": "Gratuit",
        "price": 0,
        "signals_per_day": 5,
        "execution": False,
        "risk_alerts": False,
        "daily_briefs": False,
        "api_access": False,
        "history": "24h",
        "explanations": "basic",
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "signals_per_day": -1,
        "execution": False,
        "risk_alerts": True,
        "daily_briefs": True,
        "api_access": False,
        "history": "full",
        "explanations": "detailed",
    },
    "trader": {
        "name": "Trader",
        "price": 99,
        "signals_per_day": -1,
        "execution": True,
        "risk_alerts": True,
        "daily_briefs": True,
        "api_access": True,
        "history": "full",
        "explanations": "detailed + sub-scores",
    },
}

STRIPE_PRICE_MAP = {
    "pro": "stripe_price_pro",
    "trader": "stripe_price_trader",
}


@router.get("/plans")
async def get_plans():
    return {"plans": PLANS}


@router.get("/current")
async def get_current_plan(db: AsyncSession = Depends(get_db_session)):
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
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    if plan not in ("pro", "trader"):
        raise HTTPException(status_code=400, detail="Invalid plan")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    price_attr = STRIPE_PRICE_MAP.get(plan)
    price_id = getattr(settings, price_attr, None) if price_attr else None
    if not price_id:
        raise HTTPException(status_code=503, detail=f"Stripe price for {plan} not configured")

    customer_id = user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(
            email=getattr(user, "email", None),
            metadata={"user_id": str(user.id)},
        )
        customer_id = customer.id
        user.stripe_customer_id = customer_id
        await db.commit()

    base_url = settings.app_base_url
    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        payment_method_types=["card", "link"],
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base_url}/settings?checkout=success",
        cancel_url=f"{base_url}/pricing",
        metadata={"user_id": str(user.id), "plan": plan},
        allow_promotion_codes=True,
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal(db: AsyncSession = Depends(get_db_session)):
    """Create a Stripe Customer Portal session for managing subscriptions."""
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    import stripe
    stripe.api_key = settings.stripe_secret_key

    result = await db.execute(select(UserProfile).limit(1))
    user = result.scalar_one_or_none()
    if not user or not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No active subscription")

    base_url = settings.app_base_url
    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{base_url}/settings",
    )

    return {"portal_url": session.url}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db_session)):
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
            user.stripe_subscription_id = session.get("subscription")
            await db.commit()
            logger.info("User %d upgraded to %s", user_id, plan)

    elif event["type"] == "customer.subscription.updated":
        sub = event["data"]["object"]
        customer_id = sub.get("customer")
        if customer_id:
            result = await db.execute(
                select(UserProfile).where(UserProfile.stripe_customer_id == customer_id)
            )
            user = result.scalar_one_or_none()
            if user and sub.get("status") == "active":
                plan_from_price = _plan_from_subscription(sub, settings)
                if plan_from_price:
                    user.plan = plan_from_price
                    await db.commit()

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
                user.stripe_subscription_id = None
                await db.commit()

    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        customer_id = invoice.get("customer")
        if customer_id:
            logger.warning("Payment failed for customer %s", customer_id)

    return {"status": "ok"}


def _plan_from_subscription(sub: dict, settings) -> Optional[str]:
    """Determine plan name from Stripe subscription price ID."""
    items = sub.get("items", {}).get("data", [])
    if not items:
        return None
    price_id = items[0].get("price", {}).get("id")
    if price_id == settings.stripe_price_pro:
        return "pro"
    if price_id == settings.stripe_price_trader:
        return "trader"
    return None
