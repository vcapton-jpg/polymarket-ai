"""Telegram webhook — receives updates from Telegram Bot API.

Security: the handler authenticates each request via the shared secret
that Telegram returns in the `X-Telegram-Bot-Api-Secret-Token` header.
Without this check (audit 2026-05-05) the endpoint was a textbook spoof:
anyone who could reach the public URL could POST a forged `update`
payload with an attacker-chosen `chat_id` and trigger `send_message`,
which:
  * burns the bot token's quota and may get it rate-limited,
  * leaks command output (`/signals`, `/portfolio`, etc.) to
    third-party chat IDs the attacker controls,
  * drowns the worker thread in fake updates (DoS).

Set the secret server-side as `TELEGRAM_WEBHOOK_SECRET` and pass the
*same* value when calling `setWebhook` so Telegram echoes it back. The
handler returns 401 on mismatch with no body — same shape as Telegram's
own auth failures so a probe gets nothing useful. An empty configured
secret disables the check (intended for local dev only).
"""

import hmac
import logging

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.telegram.bot import handle_command, send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = get_settings()
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your-telegram-bot-token":
        return JSONResponse({"ok": False, "detail": "Bot not configured"}, status_code=503)

    # Constant-time compare on the shared secret — `hmac.compare_digest`
    # avoids the timing oracle a naive `==` would expose.
    expected = settings.telegram_webhook_secret
    if expected:
        provided = x_telegram_bot_api_secret_token or ""
        if not hmac.compare_digest(expected, provided):
            logger.warning(
                "telegram_webhook: rejected request with bad/missing secret header "
                "(remote=%s)",
                request.client.host if request.client else "unknown",
            )
            return JSONResponse({"ok": False}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)

    message = body.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id or not text:
        return {"ok": True}

    if text.startswith("/"):
        parts = text.split()
        command = parts[0].split("@")[0]
        args = parts[1:]
        response_text = await handle_command(chat_id, command, args)
    else:
        response_text = "I only understand commands. Type /help to see what I can do."

    await send_message(chat_id, response_text)
    return {"ok": True}
