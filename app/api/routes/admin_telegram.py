"""Web admin form — Telegram session setup endpoints.

Reachable at:
  POST /api/admin/telegram/start    {api_id, api_hash, phone}
  POST /api/admin/telegram/verify   {phone, code, password?}
  GET  /api/admin/telegram/status

Auth: every endpoint reads a `X-Admin-Token` request header and matches
it (constant-time) against `settings.admin_token`. If `admin_token` is
unset/empty, every endpoint returns 403 — there is no implicit-trust
mode, the operator MUST set `ADMIN_TOKEN=<secret>` in the host `.env`
before this form is usable.

Why dispatch via `celery_app.send_task(name=...)` instead of importing
the task object: the `app` API container does NOT have `telethon`
installed. The moment we `from app.workers.tasks_telegram_admin import
tg_admin_send_code` here, the worker module is imported into the API
process — which transitively imports telethon and crashes the API at
boot. `send_task` by string name only requires the broker URL, no
worker-module import, so the trust boundary stays clean.

Why `.get(timeout=45)` instead of polling: this is a developer
one-shot (not a hot-path API), the worker prefetch_multiplier=1 on the
`ingestion` queue, and 45s comfortably covers Telethon's two 20–30s
internal timeouts plus broker round-trip overhead. If the queue is
genuinely backed up the call returns a timeout error the form can show.
"""

from __future__ import annotations

import hmac
import logging

from celery.result import AsyncResult
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/telegram", tags=["admin-telegram"])


# Synchronous wait for the celery result. 45 s is the tight upper bound
# given Telethon's two 20-30 s internal timeouts plus broker
# round-trip.
_RESULT_WAIT_SECONDS = 45


class StartBody(BaseModel):
    api_id: str
    api_hash: str
    phone: str


class VerifyBody(BaseModel):
    phone: str
    code: str
    password: str | None = None


def _check_admin_token(x_admin_token: str | None) -> None:
    """403 unless settings.admin_token is set AND matches the header."""
    settings = get_settings()
    expected = settings.admin_token or ""
    if not expected:
        # Operator did not configure ADMIN_TOKEN — fail closed.
        raise HTTPException(status_code=403, detail="admin form not configured — set ADMIN_TOKEN on the server")
    provided = x_admin_token or ""
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=403, detail="forbidden")


def _dispatch_and_wait(task_name: str, kwargs: dict) -> dict:
    """Send the task to the `ingestion` queue and return its result dict.

    On broker errors or result timeout this returns an `ok=False` dict
    rather than raising, because the HTML form is more useful if it
    surfaces the failure inline instead of getting a generic 500.
    """
    try:
        from app.workers.celery_app import celery_app
    except Exception as e:  # pragma: no cover — broker import surface
        logger.exception("admin_telegram: failed to import celery_app")
        return {"ok": False, "error": f"celery import failed: {type(e).__name__}: {e}"}

    try:
        async_result: AsyncResult = celery_app.send_task(
            task_name,
            kwargs=kwargs,
            queue="ingestion",
        )
    except Exception as e:
        logger.exception("admin_telegram: send_task failed for %s", task_name)
        return {"ok": False, "error": f"failed to enqueue task: {type(e).__name__}: {e}"}

    try:
        result = async_result.get(timeout=_RESULT_WAIT_SECONDS, disable_sync_subtasks=False)
    except Exception as e:
        logger.warning("admin_telegram: result.get timeout for %s: %s", task_name, e)
        return {"ok": False, "error": f"worker did not return in {_RESULT_WAIT_SECONDS}s ({type(e).__name__}). Check worker-ingestion logs."}

    if not isinstance(result, dict):
        return {"ok": False, "error": f"worker returned non-dict ({type(result).__name__})"}
    return result


@router.post("/start")
async def admin_telegram_start(
    body: StartBody,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    _check_admin_token(x_admin_token)
    return _dispatch_and_wait(
        "app.workers.tasks_telegram_admin.tg_admin_send_code",
        {"api_id": body.api_id, "api_hash": body.api_hash, "phone": body.phone},
    )


@router.post("/verify")
async def admin_telegram_verify(
    body: VerifyBody,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    _check_admin_token(x_admin_token)
    return _dispatch_and_wait(
        "app.workers.tasks_telegram_admin.tg_admin_verify_code",
        {"phone": body.phone, "code": body.code, "password": body.password or ""},
    )


@router.get("/status")
async def admin_telegram_status(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict:
    _check_admin_token(x_admin_token)
    settings = get_settings()
    ss = settings.telegram_session_string or ""
    return {"configured": len(ss) > 100, "len": len(ss)}
