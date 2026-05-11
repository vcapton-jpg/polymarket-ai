"""One-shot script — generate a Telethon session string for /opt/foresight/.env

USAGE (run locally on your laptop, NOT on the VPS — interactive login):

    1. Visit https://my.telegram.org/apps and create an application:
         - App title: "foresight-ingestion"
         - Short name: "foresight"
         - Platform: "Other"
       Note the `api_id` (number) and `api_hash` (32-char hex).

    2. Run this script:

         python -m app.scripts.init_telegram_session

       It will prompt for:
         - api_id      (from step 1)
         - api_hash    (from step 1)
         - phone       (your phone in international format, e.g. +33612345678)
         - code        (sent to your Telegram app)
         - password    (only if 2FA is enabled on your Telegram account)

    3. The script prints a TELEGRAM_SESSION_STRING. Paste it (along with
       api_id / api_hash) into /opt/foresight/.env on the VPS:

         TELEGRAM_API_ID=12345678
         TELEGRAM_API_HASH=abcdef1234567890abcdef1234567890
         TELEGRAM_SESSION_STRING=1AaBb...long_string...

    4. From your Telegram client, JOIN the public channels you want to
       scrape (@firstsquaw, @bloomberg, etc.). Telethon reads as your
       user, so you must be subscribed to the channel.

    5. Restart `worker-ingestion` + `beat` on the VPS to pick up the new
       env vars: `docker compose restart worker-ingestion beat`.

SECURITY: the session string is the equivalent of being logged into your
Telegram account. Treat it like a password. The .env file is gitignored
and lives only on the VPS. To revoke: Telegram app → Settings → Devices
→ Terminate the "foresight-ingestion" session.
"""

import asyncio
import getpass
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    print("=" * 60)
    print("Foresight — Telegram session string generator")
    print("=" * 60)
    api_id = input("api_id (from my.telegram.org/apps): ").strip()
    api_hash = input("api_hash: ").strip()
    if not api_id.isdigit() or len(api_hash) != 32:
        print("ERROR: api_id must be numeric, api_hash must be 32 hex chars.")
        return

    async with TelegramClient(StringSession(), int(api_id), api_hash) as client:
        # `start()` walks the user through phone -> code -> 2FA prompts
        # interactively; on success the session is persisted in `client.session`.
        await client.start(password=lambda: getpass.getpass("2FA password (blank if none): "))
        session_string = client.session.save()

    print()
    print("=" * 60)
    print("SUCCESS. Add these 3 lines to /opt/foresight/.env on the VPS:")
    print("=" * 60)
    print(f"TELEGRAM_API_ID={api_id}")
    print(f"TELEGRAM_API_HASH={api_hash}")
    print(f"TELEGRAM_SESSION_STRING={session_string}")
    print("=" * 60)

    # Also write to /tmp/tg-credentials.txt — useful when running inside a
    # container via `docker compose exec` where the parent terminal may eat
    # scrollback (Hetzner web console). Retrieve with:
    #   docker compose exec worker-ingestion cat /tmp/tg-credentials.txt
    creds_path = "/tmp/tg-credentials.txt"
    try:
        with open(creds_path, "w") as f:
            f.write(f"TELEGRAM_API_ID={api_id}\n")
            f.write(f"TELEGRAM_API_HASH={api_hash}\n")
            f.write(f"TELEGRAM_SESSION_STRING={session_string}\n")
        print(f"\nAlso written to {creds_path} (cat it if scrollback is lost).")
    except OSError as e:
        print(f"\n[warn] could not write {creds_path}: {e}")

    # If the host `.env` was mounted via docker-compose (see compose volume
    # `./.env:/opt/host-env`), patch it directly: strip out any existing
    # TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SESSION_STRING lines
    # (and any dash-cased variants left over by paste corruption) and append
    # fresh ones. This is the zero-copy-paste path for restricted consoles.
    host_env = "/opt/host-env"
    if os.path.exists(host_env) and os.access(host_env, os.W_OK):
        try:
            with open(host_env) as f:
                lines = f.readlines()
            prefixes_to_strip = (
                "TELEGRAM_API_ID=", "TELEGRAM_API_HASH=", "TELEGRAM_SESSION_STRING=",
                "TELEGRAM-API-ID=", "TELEGRAM-API-HASH=", "TELEGRAM-SESSION-STRING=",
            )
            keep = [l for l in lines if not l.startswith(prefixes_to_strip)]
            # Trim trailing blank/comment-only lines, then append cleanly
            while keep and keep[-1].strip() == "":
                keep.pop()
            keep.append("\n# Telegram user-session credentials (auto-written by init_telegram_session.py)\n")
            keep.append(f"TELEGRAM_API_ID={api_id}\n")
            keep.append(f"TELEGRAM_API_HASH={api_hash}\n")
            keep.append(f"TELEGRAM_SESSION_STRING={session_string}\n")
            with open(host_env, "w") as f:
                f.writelines(keep)
            print(f"\n✓ Updated host {host_env} directly — no copy-paste needed.")
            print("  Restart the workers to pick up the new env vars:")
            print("    docker compose -f /opt/foresight/docker-compose.yml restart worker-ingestion beat")
            return
        except OSError as e:
            print(f"\n[warn] could not patch {host_env}: {e} — fall back to manual paste below")

    print()
    print("Next steps:")
    print("  1. SSH the VPS and paste the 3 lines into /opt/foresight/.env")
    print("  2. From your Telegram client, join the channels you want to scrape")
    print("     (e.g. @firstsquaw, @bloomberg)")
    print("  3. ssh foresight 'cd /opt/foresight && docker compose restart worker-ingestion beat'")


if __name__ == "__main__":
    asyncio.run(main())
