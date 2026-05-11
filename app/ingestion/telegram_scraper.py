"""Async Telegram channel scraper — pulls messages from public channels.

Bypasses Twitter rate-limit on hot accounts (@FirstSquawk, Bloomberg, etc.)
by reading the same content from their public Telegram channels. Telegram's
MTProto API is free, has no rate-limit for normal usage, and pushes messages
within 1-2s of publication (vs ~60s for RSSHub Twitter cache).

Uses Telethon (user API, not Bot API) so we can read any public channel
where the authenticated user is subscribed — bots can only read channels
where they're admin.

Auth model:
  1. User creates a Telegram application at https://my.telegram.org/apps
     to get TELEGRAM_API_ID and TELEGRAM_API_HASH.
  2. User runs `python -m app.scripts.init_telegram_session` once locally
     with their phone number to generate a TELEGRAM_SESSION_STRING.
  3. The three values are stored in /opt/foresight/.env (gitignored).
  4. The authenticated user (not a bot) must join the channels manually
     to be able to read them from Telethon.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    ChannelPrivateError,
    FloodWaitError,
    UsernameInvalidError,
    UsernameNotOccupiedError,
)
from telethon.network import ConnectionTcpObfuscated
from telethon.sessions import StringSession
from telethon.tl.types import Channel, MessageService

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Singleton — Telethon clients are expensive to instantiate (MTProto handshake)
# and the API rewards long-lived connections. One client per worker process is
# enough; concurrent message fetches are pipelined over the same socket.
_client: Optional[TelegramClient] = None


def _build_message_url(channel_username: str, message_id: int) -> str:
    """Canonical t.me URL for a message — used as `news.url` for dedupe."""
    return f"https://t.me/{channel_username.lstrip('@')}/{message_id}"


async def get_client() -> Optional[TelegramClient]:
    """Lazy-init singleton Telethon client. Returns None if not configured."""
    global _client
    if _client is not None and _client.is_connected():
        return _client

    settings = get_settings()
    if not (
        settings.telegram_api_id
        and settings.telegram_api_hash
        and settings.telegram_session_string
    ):
        logger.warning(
            "Telegram credentials missing (TELEGRAM_API_ID / TELEGRAM_API_HASH "
            "/ TELEGRAM_SESSION_STRING). Skip telegram fetch."
        )
        return None

    try:
        logger.info("Telegram: building client (api_id=%s, session_len=%d)",
                    settings.telegram_api_id, len(settings.telegram_session_string))
        # Use ConnectionTcpObfuscated to look like generic TLS traffic — bypasses
        # the deep-packet-inspection filtering some hosting providers (notably
        # Hetzner) apply to MTProto flows, which manifests as a TCP handshake
        # that completes but then hangs on the post-handshake auth roundtrip.
        _client = TelegramClient(
            StringSession(settings.telegram_session_string),
            int(settings.telegram_api_id),
            settings.telegram_api_hash,
            connection=ConnectionTcpObfuscated,
        )
        logger.info("Telegram: connecting (timeout=15s)...")
        await asyncio.wait_for(_client.connect(), timeout=15.0)
        logger.info("Telegram: connect() OK, checking authorization (timeout=15s)...")
        is_auth = await asyncio.wait_for(_client.is_user_authorized(), timeout=15.0)
        if not is_auth:
            logger.error(
                "Telegram: NOT AUTHORIZED — session string invalid/expired or "
                "2FA password was required at init but not provided. Re-run "
                "app.scripts.init_telegram_session and update .env."
            )
            await _client.disconnect()
            _client = None
            return None
        me = await asyncio.wait_for(_client.get_me(), timeout=10.0)
        logger.info(
            "Telegram client connected as @%s (id=%s) — user session OK",
            getattr(me, "username", "<no-username>"), getattr(me, "id", "?"),
        )
        return _client
    except asyncio.TimeoutError:
        logger.error(
            "Telegram: TIMEOUT during init (>15s on connect/authorize). "
            "Likely causes: (1) Hetzner egress blocking 149.154.x.x:443 "
            "for some packets after handshake, (2) session string is for a "
            "different DC and migration hangs, (3) account requires re-auth. "
            "Drop client and retry next cycle."
        )
        try:
            if _client:
                await _client.disconnect()
        except Exception:
            pass
        _client = None
        return None
    except Exception as e:
        logger.exception("Telegram client init failed: %s", e)
        _client = None
        return None


async def fetch_channel_messages(
    channel_username: str,
    *,
    limit: int = 50,
    min_id: int = 0,
) -> list[dict]:
    """Fetch recent messages from a public Telegram channel.

    `channel_username` should be the @handle without the leading @
    (e.g. "firstsquaw", "bloomberg"). Returns a list of raw article dicts
    matching the same shape as RSS articles so downstream code is unchanged:

        {url, title, text, publish_date}

    `min_id` filters Telegram to only return messages newer than that id —
    callers pass the highest id seen previously to make this incremental.
    """
    client = await get_client()
    if client is None:
        return []

    handle = channel_username.lstrip("@")
    try:
        entity = await asyncio.wait_for(client.get_entity(handle), timeout=15.0)
    except asyncio.TimeoutError:
        logger.error("Telegram: get_entity(@%s) timeout >15s — dropping", handle)
        return []
    except (UsernameInvalidError, UsernameNotOccupiedError):
        logger.warning("Telegram channel @%s does not exist", handle)
        return []
    except ChannelPrivateError:
        logger.warning(
            "Telegram channel @%s is private — the authenticated user must "
            "join it first via Telegram client",
            handle,
        )
        return []
    except FloodWaitError as e:
        logger.warning(
            "Telegram FloodWait %ss on @%s — backing off", e.seconds, handle,
        )
        return []
    except Exception as e:
        logger.exception("Telegram get_entity failed for @%s: %s", handle, e)
        return []

    if not isinstance(entity, Channel):
        logger.warning("@%s is not a channel (got %s)", handle, type(entity).__name__)
        return []

    try:
        messages = await asyncio.wait_for(
            client.get_messages(entity, limit=limit, min_id=min_id),
            timeout=15.0,
        )
    except asyncio.TimeoutError:
        logger.error("Telegram: get_messages(@%s) timeout >15s — dropping", handle)
        return []
    except FloodWaitError as e:
        logger.warning(
            "Telegram FloodWait %ss on get_messages(@%s) — backing off",
            e.seconds, handle,
        )
        return []
    except Exception as e:
        logger.exception("Telegram get_messages failed for @%s: %s", handle, e)
        return []

    out: list[dict] = []
    for msg in messages:
        # Skip joins/leaves/pins/etc — only real content
        if isinstance(msg, MessageService):
            continue
        text = (msg.message or "").strip()
        if not text:
            continue
        # Telegram timestamps are tz-aware UTC by default
        publish_date: datetime = msg.date
        if publish_date.tzinfo is None:
            publish_date = publish_date.replace(tzinfo=timezone.utc)
        # Title = first line truncated, mirrors how RSSHub builds tweet titles
        first_line = text.split("\n", 1)[0]
        title = first_line[:240]
        out.append({
            "url": _build_message_url(handle, msg.id),
            "title": title,
            "text": text,
            "publish_date": publish_date,
            "external_id": str(msg.id),
        })
    logger.info("telegram @%s: fetched %d messages (min_id=%d)", handle, len(out), min_id)
    return out
