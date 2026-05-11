"""Web-admin Telegram session setup — Celery tasks.

These tasks run EXCLUSIVELY on `worker-ingestion` because:
  1. The `telethon` library is installed only on that image's Python
     deps (the `app` API container does not have it).
  2. The volume `./.env:/opt/host-env` is mounted only on
     `worker-ingestion` (see docker-compose.yml). The host `.env` patch
     therefore has to happen from this worker, not from the FastAPI
     process.

Why a web admin path at all: the prior interactive script
(`app/scripts/init_telegram_session.py`) requires running
`docker compose exec worker-ingestion python …` from the Hetzner web
console, whose keymap mangles characters (`_`, `^`, `|`) needed for the
`init_telegram_session.py` path. The 2026-05-10 sessions burned 3+
hours debugging that. This module gives the operator a browser form
instead.

Flow:
  /api/admin/telegram/start  → tg_admin_send_code
        Telethon connect → send_code_request → stash {api_id, api_hash,
        phone, phone_code_hash} in Redis under tg_admin:pending:{phone}
        with TTL 600s.
  /api/admin/telegram/verify → tg_admin_verify_code
        Read stash from Redis → sign_in(code) → optional 2FA →
        session.save() → patch /opt/host-env (strip old lines, append
        fresh) → verify by re-reading → delete Redis stash.

Security: the calling FastAPI route gates both endpoints behind
`X-Admin-Token`. Without that header (or with a wrong value), the route
never dispatches the task. The Celery task itself does not re-check
because the task name is not enqueueable from outside `app` (the same
trust boundary already applies to every other task in this repo).
"""

import asyncio
import json
import logging
import os

logger = logging.getLogger(__name__)


_HOST_ENV = "/opt/host-env"
_REDIS_KEY_FMT = "tg_admin:pending:{phone}"
_REDIS_TTL_SECONDS = 600
_PENDING_FIELDS = ("api_id", "api_hash", "phone", "phone_code_hash")


# ── Lazy imports ──────────────────────────────────────────────────────
# Celery autodiscovers this module via `celery_app.autodiscover_tasks`,
# which means the worker imports it at boot. Telethon is heavy (~50 MB
# RSS, lots of submodules) and the worker should not pay that cost
# unless an admin actually triggers a session setup. Keep the import at
# call-site inside the task body.


def _redis_client():
    """Return a sync redis client bound to settings.redis_url DB 0."""
    import redis

    from app.core.config import get_settings

    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _build_client(api_id: str, api_hash: str, session_str: str = ""):
    """Build a TelegramClient with ConnectionTcpObfuscated.

    Hetzner egress IPs are DPI-classified on the default plaintext
    MTProto port. The obfuscated transport bypasses that — see
    c195f2e on fix/telegram-obfuscated-connection.

    `session_str` lets the caller resume an existing Telethon session
    (auth_key + DC routing). When empty, a fresh StringSession() is used.
    Critical for the send_code → verify_code round-trip: the
    `phone_code_hash` returned by send_code_request is tied to the
    auth_key of the connecting client. If verify_code spins up a
    brand-new session, Telegram refuses the hash with PhoneCodeExpired
    even though the user-facing code is still fresh. Reuse the session
    string we serialised after send_code to keep the same auth_key.
    """
    from telethon import TelegramClient
    from telethon.network import ConnectionTcpObfuscated
    from telethon.sessions import StringSession

    return TelegramClient(
        StringSession(session_str) if session_str else StringSession(),
        int(api_id),
        api_hash,
        connection=ConnectionTcpObfuscated,
    )


def _patch_host_env(api_id: str, api_hash: str, session_string: str) -> tuple[bool, str]:
    """Strip old TELEGRAM_* lines from /opt/host-env and append fresh.

    Returns (ok, message). On verification failure (re-read does not
    show the new SESSION_STRING) returns (False, reason). Mirrors the
    logic of init_telegram_session.py step 6.
    """
    if not os.path.exists(_HOST_ENV):
        return False, (
            f"{_HOST_ENV} does not exist — the volume mount "
            "'./.env:/opt/host-env' is not in effect on this worker. "
            "Run `docker compose up -d --force-recreate worker-ingestion`."
        )
    if not os.access(_HOST_ENV, os.W_OK):
        return False, f"{_HOST_ENV} is not writable by the worker container — check host file perms."

    try:
        with open(_HOST_ENV) as f:
            lines = f.readlines()
        prefixes = (
            "TELEGRAM_API_ID=", "TELEGRAM_API_HASH=", "TELEGRAM_SESSION_STRING=",
            "TELEGRAM-API-ID=", "TELEGRAM-API-HASH=", "TELEGRAM-SESSION-STRING=",
        )
        keep = [l for l in lines if not l.startswith(prefixes)]
        while keep and keep[-1].strip() == "":
            keep.pop()
        keep.append("\n# Telegram user-session credentials (auto-written by web admin form)\n")
        keep.append(f"TELEGRAM_API_ID={api_id}\n")
        keep.append(f"TELEGRAM_API_HASH={api_hash}\n")
        keep.append(f"TELEGRAM_SESSION_STRING={session_string}\n")
        with open(_HOST_ENV, "w") as f:
            f.writelines(keep)
    except OSError as e:
        return False, f"failed to write {_HOST_ENV}: {e}"

    # Re-read to verify
    try:
        with open(_HOST_ENV) as f:
            after = f.read()
    except OSError as e:
        return False, f"failed to re-read {_HOST_ENV} after write: {e}"

    expected = f"TELEGRAM_SESSION_STRING={session_string}"
    if expected not in after:
        return False, "verification failed — SESSION_STRING line not found after write."

    return True, "ok"


# ── async cores ───────────────────────────────────────────────────────


async def _async_send_code(api_id: str, api_hash: str, phone: str) -> dict:
    client = _build_client(api_id, api_hash)
    try:
        await asyncio.wait_for(client.connect(), timeout=20.0)
    except asyncio.TimeoutError:
        return {"ok": False, "error": "timeout connecting to Telegram MTProto (>20s) — Hetzner egress may be DPI-blocked"}
    except Exception as e:
        return {"ok": False, "error": f"connect failed: {type(e).__name__}: {e}"}

    try:
        try:
            sent = await asyncio.wait_for(client.send_code_request(phone), timeout=20.0)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout calling send_code_request (>20s)"}
        except Exception as e:
            return {"ok": False, "error": f"send_code_request failed: {type(e).__name__}: {e}"}

        phone_code_hash = getattr(sent, "phone_code_hash", None)
        if not phone_code_hash:
            return {"ok": False, "error": "telegram returned no phone_code_hash — cannot proceed"}

        # Serialise the pre-auth session string so verify_code can resume
        # with the same auth_key. Without this, Telegram returns
        # PhoneCodeExpiredError because the hash is tied to this auth.
        session_str = client.session.save()

        # Stash in Redis (DB 0) so the verify task can pick up.
        try:
            r = _redis_client()
            r.set(
                _REDIS_KEY_FMT.format(phone=phone),
                json.dumps({
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "phone": phone,
                    "phone_code_hash": phone_code_hash,
                    "session_str": session_str,
                }),
                ex=_REDIS_TTL_SECONDS,
            )
        except Exception as e:
            return {"ok": False, "error": f"failed to stash pending state in redis: {type(e).__name__}: {e}"}

        return {"ok": True, "message": "Code sent — check your Telegram app"}
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def _async_verify_code(phone: str, code: str, password: str) -> dict:
    from telethon.errors import (
        PasswordHashInvalidError,
        PhoneCodeExpiredError,
        PhoneCodeInvalidError,
        SessionPasswordNeededError,
    )

    # Pull pending state
    try:
        r = _redis_client()
        raw = r.get(_REDIS_KEY_FMT.format(phone=phone))
    except Exception as e:
        return {"ok": False, "error": f"redis read failed: {type(e).__name__}: {e}"}
    if not raw:
        return {"ok": False, "error": "no pending code for this phone — call /start first"}
    try:
        state = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "pending state in redis is corrupted — call /start again"}
    missing = [k for k in _PENDING_FIELDS if not state.get(k)]
    if missing:
        return {"ok": False, "error": f"pending state missing fields {missing} — call /start again"}

    api_id = state["api_id"]
    api_hash = state["api_hash"]
    phone_code_hash = state["phone_code_hash"]
    session_str = state.get("session_str", "")

    client = _build_client(api_id, api_hash, session_str=session_str)
    try:
        try:
            await asyncio.wait_for(client.connect(), timeout=20.0)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout connecting to Telegram MTProto (>20s)"}
        except Exception as e:
            return {"ok": False, "error": f"connect failed: {type(e).__name__}: {e}"}

        # First sign-in attempt with code
        try:
            await asyncio.wait_for(
                client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash),
                timeout=30.0,
            )
        except PhoneCodeInvalidError:
            return {"ok": False, "error": "invalid code — request a fresh one via /start"}
        except PhoneCodeExpiredError:
            return {"ok": False, "error": "code expired — request a fresh one via /start"}
        except SessionPasswordNeededError:
            if not password:
                return {"ok": False, "error": "2FA password required — re-submit with password field"}
            try:
                await asyncio.wait_for(client.sign_in(password=password), timeout=30.0)
            except PasswordHashInvalidError:
                return {"ok": False, "error": "wrong 2FA password"}
            except asyncio.TimeoutError:
                return {"ok": False, "error": "timeout submitting 2FA password (>30s)"}
            except Exception as e:
                return {"ok": False, "error": f"2FA sign-in failed: {type(e).__name__}: {e}"}
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout submitting code (>30s)"}
        except Exception as e:
            return {"ok": False, "error": f"sign_in failed: {type(e).__name__}: {e}"}

        # Verify authorization
        try:
            is_auth = await asyncio.wait_for(client.is_user_authorized(), timeout=10.0)
        except asyncio.TimeoutError:
            is_auth = False
        if not is_auth:
            return {"ok": False, "error": "client is not authorized after sign_in (unexpected)"}

        try:
            me = await asyncio.wait_for(client.get_me(), timeout=10.0)
        except Exception as e:
            return {"ok": False, "error": f"get_me failed: {type(e).__name__}: {e}"}

        session_string = client.session.save()
        if not session_string or len(session_string) < 100:
            return {"ok": False, "error": f"session string is too short ({len(session_string or '')} chars) — refusing to write a bad credential"}

        # Write to host .env
        ok, msg = _patch_host_env(api_id, api_hash, session_string)
        if not ok:
            return {"ok": False, "error": msg}

        # Cleanup the Redis stash
        try:
            r = _redis_client()
            r.delete(_REDIS_KEY_FMT.format(phone=phone))
        except Exception:
            # Non-fatal: TTL will clean up in 10 min.
            logger.warning("tg_admin_verify_code: failed to delete redis stash for phone=%s", phone)

        return {
            "ok": True,
            "username": me.username,
            "id": me.id,
            "session_len": len(session_string),
        }
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


# ── Celery task wrappers ──────────────────────────────────────────────


def _register_tasks() -> None:
    """Bind the two tasks onto celery_app. Called at module import."""
    from app.workers.celery_app import celery_app

    @celery_app.task(
        name="app.workers.tasks_telegram_admin.tg_admin_send_code",
        queue="ingestion",
        ignore_result=False,
    )
    def tg_admin_send_code(api_id: str, api_hash: str, phone: str) -> dict:
        try:
            return asyncio.run(_async_send_code(api_id, api_hash, phone))
        except Exception as e:
            logger.exception("tg_admin_send_code crashed")
            return {"ok": False, "error": f"task crash: {type(e).__name__}: {e}"}

    @celery_app.task(
        name="app.workers.tasks_telegram_admin.tg_admin_verify_code",
        queue="ingestion",
        ignore_result=False,
    )
    def tg_admin_verify_code(phone: str, code: str, password: str = "") -> dict:
        try:
            return asyncio.run(_async_verify_code(phone, code, password or ""))
        except Exception as e:
            logger.exception("tg_admin_verify_code crashed")
            return {"ok": False, "error": f"task crash: {type(e).__name__}: {e}"}

    # Expose at module level so `from app.workers.tasks_telegram_admin
    # import tg_admin_send_code` works for tests / introspection. Not used
    # by the dispatcher, which goes through send_task by name.
    globals()["tg_admin_send_code"] = tg_admin_send_code
    globals()["tg_admin_verify_code"] = tg_admin_verify_code


_register_tasks()
