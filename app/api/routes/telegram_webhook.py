"""Telegram webhook — receives updates from Telegram Bot API."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.telegram.bot import handle_command, send_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(request: Request):
    settings = get_settings()
    if not settings.telegram_bot_token or settings.telegram_bot_token == "your-telegram-bot-token":
        return JSONResponse({"ok": False, "detail": "Bot not configured"}, status_code=503)

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
