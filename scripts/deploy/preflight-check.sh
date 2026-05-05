#!/usr/bin/env bash
# Pre-flight check — validates the production .env BEFORE you boot
# the stack. Refuses to pass if any setting matches a known-insecure
# default or is missing in a context where it's required.
#
# Run from the repo root:
#   $ bash scripts/deploy/preflight-check.sh
#
# Exit codes:
#   0  — all checks passed, safe to `docker compose up`
#   1  — one or more checks failed, fix .env and re-run
#
# This script DOES NOT print any secret values. Failures show only the
# variable name and a remediation hint — copy-pasting the output to
# Slack / email is safe.

set -uo pipefail

ENV_FILE="${ENV_FILE:-.env}"
FAIL=0
PASS=0

red()    { printf '\033[31m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }

if [ ! -f "$ENV_FILE" ]; then
    red "FAIL: $ENV_FILE not found. Run \`cp scripts/deploy/production.env.template .env\` first."
    exit 1
fi

# Read a var without exporting (safe if .env contains shell metacharacters).
get() {
    grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

require() {
    local name="$1"
    local hint="$2"
    local val
    val="$(get "$name")"
    if [ -z "$val" ]; then
        red "FAIL: $name is empty.  $hint"
        FAIL=$((FAIL + 1))
    else
        green "OK:   $name is set"
        PASS=$((PASS + 1))
    fi
}

reject() {
    # Fails if the var matches one of the bad values.
    local name="$1"
    shift
    local hint="$1"
    shift
    local val
    val="$(get "$name")"
    for bad in "$@"; do
        if [ "$val" = "$bad" ]; then
            red "FAIL: $name is set to a known-insecure default.  $hint"
            FAIL=$((FAIL + 1))
            return
        fi
    done
    if [ -n "$val" ]; then
        green "OK:   $name passes default-value check"
        PASS=$((PASS + 1))
    fi
}

contains() {
    # Fails if the var contains the given substring (case-insensitive).
    local name="$1"
    local needle="$2"
    local hint="$3"
    local val
    val="$(get "$name")"
    if echo "$val" | grep -qi "$needle"; then
        red "FAIL: $name contains '$needle'.  $hint"
        FAIL=$((FAIL + 1))
    fi
}

echo "═════════════════════════════════════════════════════════════════════"
echo "  Foresight pre-flight check"
echo "  ENV_FILE=$ENV_FILE"
echo "═════════════════════════════════════════════════════════════════════"

# ── Environment ──
ENV_VAL="$(get ENV)"
case "$ENV_VAL" in
    production)
        green "OK:   ENV=production"
        PASS=$((PASS + 1))
        IS_PROD=1
        ;;
    staging|preview|qa|uat|demo)
        yellow "WARN: ENV=$ENV_VAL — non-local env, treating as production-strict"
        IS_PROD=1
        ;;
    development|dev|test|testing|local|"")
        yellow "WARN: ENV=$ENV_VAL — running pre-flight in dev mode (lax checks)"
        IS_PROD=0
        ;;
    *)
        red "FAIL: ENV=$ENV_VAL is not a recognised value.  Set ENV to one of: production, staging, development."
        FAIL=$((FAIL + 1))
        IS_PROD=1  # fail closed
        ;;
esac

# ── Database ──
require DATABASE_URL "Set DATABASE_URL=postgresql+asyncpg://postgres:<strong-pwd>@db:5432/signal"
require DATABASE_URL_SYNC "Set DATABASE_URL_SYNC=postgresql+psycopg://postgres:<strong-pwd>@db:5432/signal"
if [ "$IS_PROD" = 1 ]; then
    contains DATABASE_URL "postgres:postgres" "Default DB password — generate one with \`openssl rand -hex 24\`."
    contains DATABASE_URL "postgres:password" "Default-ish DB password — generate one with \`openssl rand -hex 24\`."
    contains DATABASE_URL_SYNC "postgres:postgres" "DATABASE_URL_SYNC must use the same strong password."
    contains DATABASE_URL "@localhost" "Production DATABASE_URL should reference the docker-compose service name (\`@db:\`), not localhost."
    contains POSTGRES_PASSWORD "postgres" "POSTGRES_PASSWORD must match the password in DATABASE_URL — and not be \`postgres\`."
fi

# ── Redis ──
require REDIS_URL "Set REDIS_URL=redis://redis:6379/0"

# ── JWT ──
require JWT_SECRET_KEY "Generate: \`openssl rand -hex 32\`"
if [ "$IS_PROD" = 1 ]; then
    reject JWT_SECRET_KEY \
        "Generate a real one: \`openssl rand -hex 32\`" \
        "change-me-in-production" \
        "foresight-dev-secret-key-change-in-prod-2026" \
        "GENERATE_WITH_openssl_rand_hex_32"
    JWT_VAL="$(get JWT_SECRET_KEY)"
    JWT_LEN=${#JWT_VAL}
    if [ "$JWT_LEN" -lt 32 ]; then
        red "FAIL: JWT_SECRET_KEY is only $JWT_LEN chars — too short. Use \`openssl rand -hex 32\` (64 chars)."
        FAIL=$((FAIL + 1))
    fi
fi

# ── OpenAI ──
require OPENAI_API_KEY "Get one at https://platform.openai.com/api-keys"
contains OPENAI_API_KEY "sk-proj-d_0dV" "OPENAI_API_KEY appears to match the leaked key from .env.backup-2026-04-27. Rotate it."

# ── Telegram (only required if bot is wired) ──
TELEGRAM_TOKEN_VAL="$(get TELEGRAM_BOT_TOKEN)"
if [ -n "$TELEGRAM_TOKEN_VAL" ] && [ "$TELEGRAM_TOKEN_VAL" != "your-telegram-bot-token" ]; then
    if [ "$IS_PROD" = 1 ]; then
        require TELEGRAM_WEBHOOK_SECRET "Generate: \`openssl rand -hex 32\` — and pass the same value to setWebhook"
        reject TELEGRAM_WEBHOOK_SECRET \
            "Generate: \`openssl rand -hex 32\`" \
            "GENERATE_WITH_openssl_rand_hex_32"
    fi
else
    yellow "WARN: TELEGRAM_BOT_TOKEN is empty — Telegram routes are disabled (this is fine if you're not using the bot)"
fi

# ── DB echo (the OOM trigger) ──
DB_ECHO_VAL="$(get DB_ECHO)"
case "$(echo "$DB_ECHO_VAL" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes)
        red "FAIL: DB_ECHO=$DB_ECHO_VAL — this caused the 6-day outage (PR #43). Leave unset in prod."
        FAIL=$((FAIL + 1))
        ;;
    *)
        green "OK:   DB_ECHO is unset / falsy"
        PASS=$((PASS + 1))
        ;;
esac

# ── CORS in production must NOT be a wildcard ──
if [ "$IS_PROD" = 1 ]; then
    CORS_VAL="$(get CORS_ORIGINS)"
    if [ "$CORS_VAL" = "*" ]; then
        red "FAIL: CORS_ORIGINS=* in production — restrict to your domain only."
        FAIL=$((FAIL + 1))
    elif [ -z "$CORS_VAL" ]; then
        yellow "WARN: CORS_ORIGINS is empty — frontend domain access will fall back to the app's default allow-list."
    else
        green "OK:   CORS_ORIGINS is set and not a wildcard"
        PASS=$((PASS + 1))
    fi

    APP_BASE_URL_VAL="$(get APP_BASE_URL)"
    if echo "$APP_BASE_URL_VAL" | grep -qiE "(localhost|127\.0\.0\.1)"; then
        red "FAIL: APP_BASE_URL=$APP_BASE_URL_VAL points at localhost — set it to your production domain."
        FAIL=$((FAIL + 1))
    fi
fi

# ── LLM cost cap ──
LLM_COST_VAL="$(get LLM_COST_ALERT_USD)"
if [ -z "$LLM_COST_VAL" ]; then
    yellow "WARN: LLM_COST_ALERT_USD is unset — using app default (30 USD)."
elif [ "$IS_PROD" = 1 ]; then
    # Numeric sanity (any "0" or empty fails on this pattern below)
    case "$LLM_COST_VAL" in
        0|0.0|0.00) yellow "WARN: LLM_COST_ALERT_USD=0 disables the breaker. OK for dev only." ;;
        *) green "OK:   LLM_COST_ALERT_USD=$LLM_COST_VAL"; PASS=$((PASS + 1)) ;;
    esac
fi

# ── .env hygiene ──
if [ -f .env.backup ] || ls .env.backup-* 2>/dev/null | head -1 > /dev/null; then
    red "FAIL: .env.backup* file(s) found in repo root — delete (PR #45 lesson). Backups belong outside the repo."
    FAIL=$((FAIL + 1))
fi

# ── Summary ──
echo "═════════════════════════════════════════════════════════════════════"
if [ "$FAIL" -eq 0 ]; then
    green "  All checks passed ($PASS green)"
    echo "  Safe to run \`docker compose up -d\`."
    echo "═════════════════════════════════════════════════════════════════════"
    exit 0
else
    red "  $FAIL check(s) FAILED, $PASS passed"
    echo "  Fix the issues above and re-run this script."
    echo "═════════════════════════════════════════════════════════════════════"
    exit 1
fi
