"""Push notification subscription management and sending."""

import json
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

SUBSCRIPTIONS_KEY = "push:subscriptions"


class PushSubscription(BaseModel):
    endpoint: str
    keys: dict


@router.post("/push/subscribe")
async def subscribe_push(sub: PushSubscription):
    """Register a push notification subscription."""
    try:
        import redis as _redis
        settings = get_settings()
        r = _redis.from_url(settings.redis_url)
        r.sadd(SUBSCRIPTIONS_KEY, json.dumps(sub.model_dump()))
        r.close()
        return {"status": "ok"}
    except Exception as e:
        logger.warning("Failed to store push subscription: %s", e)
        raise HTTPException(status_code=500, detail="Failed to register")


@router.delete("/push/unsubscribe")
async def unsubscribe_push(sub: PushSubscription):
    """Remove a push notification subscription."""
    try:
        import redis as _redis
        settings = get_settings()
        r = _redis.from_url(settings.redis_url)
        r.srem(SUBSCRIPTIONS_KEY, json.dumps(sub.model_dump()))
        r.close()
        return {"status": "ok"}
    except Exception as e:
        logger.warning("Failed to remove push subscription: %s", e)
        raise HTTPException(status_code=500, detail="Failed to unsubscribe")


def send_push_to_all(title: str, body: str, url: str = "/dashboard", tag: str | None = None):
    """Send a push notification to all registered subscribers.
    Called from tasks_scoring when a high-value signal is created."""
    try:
        import redis as _redis
        from pywebpush import WebPushException, webpush
        settings = get_settings()

        vapid_private = settings.vapid_private_key
        vapid_email = settings.vapid_email
        if not vapid_private:
            logger.debug("VAPID not configured, skipping push notifications")
            return

        r = _redis.from_url(settings.redis_url)
        subs = r.smembers(SUBSCRIPTIONS_KEY)
        r.close()

        payload = json.dumps({"title": title, "body": body, "url": url, "tag": tag or "signal"})
        dead = []

        for raw in subs:
            sub_data = json.loads(raw)
            try:
                webpush(
                    subscription_info=sub_data,
                    data=payload,
                    vapid_private_key=vapid_private,
                    vapid_claims={"sub": f"mailto:{vapid_email}"},
                )
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    dead.append(raw)
                logger.debug("Push failed for %s: %s", sub_data.get("endpoint", "?")[:50], e)
            except Exception:
                logger.debug("Push send error", exc_info=True)

        if dead:
            r2 = _redis.from_url(settings.redis_url)
            for d in dead:
                r2.srem(SUBSCRIPTIONS_KEY, d)
            r2.close()

        logger.info("Push notifications sent to %d subscribers (%d dead removed)", len(subs), len(dead))

    except ImportError:
        logger.debug("pywebpush not installed, skipping push notifications")
    except Exception:
        logger.warning("Push notification broadcast failed", exc_info=True)
