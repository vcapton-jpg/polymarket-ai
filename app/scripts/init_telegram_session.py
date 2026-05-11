"""One-shot script — generate a Telethon session string for /opt/foresight/.env

USAGE (run inside the worker-ingestion container from Hetzner web console):

    docker compose -f /opt/foresight/docker-compose.yml exec worker-ingestion \\
        sh -c 'python /app/app/scripts/init*telegram*.py'

The script walks you through 6 explicit steps with validation at every
point — if anything fails, you'll see EXACTLY where, not a silent fail.

After the volume `./.env:/opt/host-env` is mounted (docker-compose), the
script patches the host `.env` directly. No copy-paste needed.

SECURITY: the session string is the equivalent of being logged into your
Telegram account. Treat it like a password. The .env file is gitignored
and lives only on the VPS. To revoke: Telegram app → Settings → Devices
→ Terminate the "foresight 1.43.2" session.
"""

import asyncio
import getpass
import os
import sys

from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

HOST_ENV = "/opt/host-env"
CREDS_PATH = "/tmp/tg-credentials.txt"


def banner(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


def prompt(label: str, validator=None) -> str:
    """Read a line of input, optionally validate. Empty input → re-prompt."""
    while True:
        value = input(label).strip()
        if not value:
            print("  (empty input — try again)")
            continue
        if validator is not None:
            error = validator(value)
            if error:
                print(f"  ERROR: {error} — try again")
                continue
        return value


def _validate_api_id(v: str) -> str | None:
    return None if v.isdigit() and len(v) >= 5 else "api_id must be all digits, ≥5 chars"


def _validate_api_hash(v: str) -> str | None:
    return None if len(v) == 32 and all(c in "0123456789abcdef" for c in v.lower()) else "api_hash must be 32 hex chars"


def _validate_phone(v: str) -> str | None:
    return None if v.startswith("+") and v[1:].isdigit() and 8 <= len(v) <= 16 else "phone must be in international format e.g. +33612345678"


async def main() -> int:
    banner("Foresight — Telegram session generator (bulletproof v2)")
    print("This script will walk through 6 steps. If anything fails, you'll")
    print("see exactly where. Do NOT Ctrl+C mid-flow.")

    # ── STEP 1/6 — collect credentials ─────────────────────────────────
    banner("STEP 1/6 — credentials")
    api_id = prompt("  api_id  (from my.telegram.org/apps): ", _validate_api_id)
    api_hash = prompt("  api_hash: ", _validate_api_hash)
    phone = prompt("  phone   (e.g. +33612345678): ", _validate_phone)
    print("  ✓ credentials look valid")

    # ── STEP 2/6 — build + connect Telethon client ─────────────────────
    banner("STEP 2/6 — connecting to Telegram")
    client = TelegramClient(StringSession(), int(api_id), api_hash)
    try:
        await asyncio.wait_for(client.connect(), timeout=20.0)
    except asyncio.TimeoutError:
        print("  ✗ TIMEOUT during connect (>20s). Network blocked? Aborting.")
        return 1
    print("  ✓ connected to Telegram MTProto")

    # ── STEP 3/6 — send code (Telegram will push it to your app) ───────
    banner("STEP 3/6 — sending login code")
    try:
        sent = await asyncio.wait_for(client.send_code_request(phone), timeout=20.0)
        print(f"  ✓ code request sent (type={getattr(sent, 'type', '?').__class__.__name__})")
        print("    → CHECK YOUR TELEGRAM APP for an incoming message")
        print("      from the 'Telegram' service — it contains a 5-digit code.")
    except asyncio.TimeoutError:
        print("  ✗ TIMEOUT sending code request. Aborting.")
        await client.disconnect()
        return 2
    except Exception as e:
        print(f"  ✗ FAILED to send code: {type(e).__name__}: {e}")
        await client.disconnect()
        return 2

    # ── STEP 4/6 — submit code (and 2FA password if required) ──────────
    banner("STEP 4/6 — login with code")
    code = prompt("  code (5 digits, from Telegram app): ")
    try:
        await asyncio.wait_for(
            client.sign_in(phone=phone, code=code),
            timeout=30.0,
        )
        print("  ✓ signed in successfully")
    except PhoneCodeInvalidError:
        print("  ✗ INVALID code. Aborting — re-run the script and use a fresh code.")
        await client.disconnect()
        return 3
    except PhoneCodeExpiredError:
        print("  ✗ CODE EXPIRED. Aborting — re-run the script faster.")
        await client.disconnect()
        return 3
    except SessionPasswordNeededError:
        print("  → 2FA password required (cloud password on this Telegram account)")
        try:
            pw = getpass.getpass("  2FA password: ")
            await asyncio.wait_for(client.sign_in(password=pw), timeout=30.0)
            print("  ✓ signed in successfully (with 2FA)")
        except PasswordHashInvalidError:
            print("  ✗ WRONG 2FA password. Aborting.")
            await client.disconnect()
            return 3
        except Exception as e:
            print(f"  ✗ 2FA sign-in failed: {type(e).__name__}: {e}")
            await client.disconnect()
            return 3
    except Exception as e:
        print(f"  ✗ sign-in failed: {type(e).__name__}: {e}")
        await client.disconnect()
        return 3

    # ── STEP 5/6 — verify authorization + save session ─────────────────
    banner("STEP 5/6 — verify auth + serialize session")
    try:
        is_auth = await asyncio.wait_for(client.is_user_authorized(), timeout=10.0)
    except asyncio.TimeoutError:
        is_auth = False
    if not is_auth:
        print("  ✗ client is NOT authorized after sign_in (unexpected). Aborting.")
        await client.disconnect()
        return 4
    me = await asyncio.wait_for(client.get_me(), timeout=10.0)
    print(f"  ✓ authorized as: {me.first_name} (@{me.username or '<no-username>'} id={me.id})")
    session_string = client.session.save()
    await client.disconnect()
    if not session_string or len(session_string) < 100:
        print(f"  ✗ session string is too short ({len(session_string)} chars) — refusing to write a bad credential. Aborting.")
        return 4
    print(f"  ✓ session string serialized ({len(session_string)} chars)")

    # ── STEP 6/6 — write host .env + tmp backup ────────────────────────
    banner("STEP 6/6 — writing credentials")

    # Backup to /tmp first (in case host .env mount missing)
    try:
        with open(CREDS_PATH, "w") as f:
            f.write(f"TELEGRAM_API_ID={api_id}\n")
            f.write(f"TELEGRAM_API_HASH={api_hash}\n")
            f.write(f"TELEGRAM_SESSION_STRING={session_string}\n")
        print(f"  ✓ written to container path {CREDS_PATH}")
    except OSError as e:
        print(f"  [warn] could not write {CREDS_PATH}: {e}")

    # Now the main event: patch host .env via volume mount
    if not os.path.exists(HOST_ENV):
        print(f"  ✗ {HOST_ENV} does NOT exist. The volume mount './.env:/opt/host-env'")
        print(f"    is not in effect. Run from the host: docker compose up -d --force-recreate worker-ingestion")
        print(f"    Then re-run this script. Manual fallback below.")
        _print_manual_fallback(api_id, api_hash, session_string)
        return 5

    if not os.access(HOST_ENV, os.W_OK):
        print(f"  ✗ {HOST_ENV} is not writable by this container. Check file perms on host.")
        _print_manual_fallback(api_id, api_hash, session_string)
        return 5

    try:
        with open(HOST_ENV) as f:
            lines = f.readlines()
        prefixes = (
            "TELEGRAM_API_ID=", "TELEGRAM_API_HASH=", "TELEGRAM_SESSION_STRING=",
            "TELEGRAM-API-ID=", "TELEGRAM-API-HASH=", "TELEGRAM-SESSION-STRING=",
        )
        keep = [l for l in lines if not l.startswith(prefixes)]
        while keep and keep[-1].strip() == "":
            keep.pop()
        keep.append("\n# Telegram user-session credentials (auto-written by init_telegram_session.py)\n")
        keep.append(f"TELEGRAM_API_ID={api_id}\n")
        keep.append(f"TELEGRAM_API_HASH={api_hash}\n")
        keep.append(f"TELEGRAM_SESSION_STRING={session_string}\n")
        with open(HOST_ENV, "w") as f:
            f.writelines(keep)
    except OSError as e:
        print(f"  ✗ failed to write {HOST_ENV}: {e}")
        _print_manual_fallback(api_id, api_hash, session_string)
        return 5

    # Verify by re-reading
    with open(HOST_ENV) as f:
        after = f.read()
    expected_ss_line = f"TELEGRAM_SESSION_STRING={session_string}"
    if expected_ss_line not in after:
        print(f"  ✗ verification failed — SESSION_STRING line not found after write. Aborting.")
        return 5

    print(f"  ✓ host .env patched and verified — SESSION_STRING is {len(session_string)} chars long")

    # ── Final banner ───────────────────────────────────────────────────
    banner("✓✓✓ DONE — Telegram session installed ✓✓✓")
    print("Next steps (from the host shell):")
    print("  1. (Telegram app) join the channels you want to scrape:")
    print("     @firstsquaw, @bloomberg, etc.")
    print("  2. Restart workers:")
    print("     docker compose -f /opt/foresight/docker-compose.yml restart worker-ingestion beat")
    print("  3. Verify in 60s: tail logs for 'Telegram client connected as @...'")
    print()
    return 0


def _print_manual_fallback(api_id: str, api_hash: str, session_string: str) -> None:
    print()
    print("FALLBACK — manually add these 3 lines to /opt/foresight/.env:")
    print("-" * 60)
    print(f"TELEGRAM_API_ID={api_id}")
    print(f"TELEGRAM_API_HASH={api_hash}")
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    print("-" * 60)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n✗ aborted by user (Ctrl+C). No changes written.")
        sys.exit(130)
