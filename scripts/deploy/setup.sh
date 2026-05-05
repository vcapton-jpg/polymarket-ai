#!/usr/bin/env bash
# Foresight VPS bootstrap — runs on a freshly-provisioned Ubuntu 24.04
# host and brings the box from "blank Ubuntu" to "Caddy + systemd unit
# ready, .env stub waiting for secrets" in ~5 minutes.
#
# Usage (one-liner from your laptop, or pasted into the VPS shell):
#   curl -fsSL https://raw.githubusercontent.com/vcapton-jpg/polymarket-ai/main/scripts/deploy/setup.sh | bash
#
# Or if you've already cloned the repo:
#   bash scripts/deploy/setup.sh
#
# What the script DOES:
#   - System update + UFW firewall (SSH/HTTP/HTTPS only)
#   - Install Docker + Compose + git + caddy + a few QoL tools
#   - Clone the repo to /opt/foresight (or git pull if already present)
#   - Generate /etc/caddy/Caddyfile from the template, with the real
#     domain (default: yourforesight.com — override via DOMAIN=)
#   - Install systemd unit so the stack auto-starts at boot
#   - Wire the daily Postgres backup cron
#   - Copy production.env.template to /opt/foresight/.env if absent
#
# What the script DOES NOT do (operator action required after):
#   1. Fill /opt/foresight/.env with real rotated secrets
#   2. Run `bash scripts/deploy/preflight-check.sh` — it must pass
#   3. `cd /opt/foresight && docker compose up -d`
#   4. Register the Telegram webhook (if bot is wired)
#
# This split is intentional: the script can run unattended on any new
# VPS, but secret material is never embedded in version control or
# transferred over the wire as part of the bootstrap. The operator
# pastes secrets manually exactly once, after the script finishes.

set -euo pipefail

# ── Config (override via env when piping) ─────────────────────────────
DOMAIN="${DOMAIN:-yourforesight.com}"
REPO_URL="${REPO_URL:-https://github.com/vcapton-jpg/polymarket-ai.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/foresight}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/foresight}"

# ── Helpers ───────────────────────────────────────────────────────────
RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'; NC=$'\033[0m'
say()  { printf "${BLUE}[setup]${NC} %s\n" "$*"; }
ok()   { printf "${GREEN}[ ok ]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[warn]${NC} %s\n" "$*" >&2; }
die()  { printf "${RED}[FAIL]${NC} %s\n" "$*" >&2; exit 1; }

# ── Pre-flight ────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || die "Run as root (the bootstrap installs system packages). Try: sudo -i"

if [ ! -f /etc/os-release ]; then
    die "/etc/os-release missing — refusing to guess the distro"
fi
. /etc/os-release
case "$ID:$VERSION_ID" in
    ubuntu:24.04|ubuntu:22.04|debian:12) ok "OS detected: $PRETTY_NAME" ;;
    *) warn "OS $PRETTY_NAME not in the tested list (ubuntu 22.04/24.04, debian 12). Continuing anyway." ;;
esac

# ── Step 1: system update + base tools ────────────────────────────────
say "Updating apt + installing base packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    git nano htop curl ca-certificates \
    ufw \
    debian-keyring debian-archive-keyring apt-transport-https
ok "Base packages installed"

# ── Step 2: firewall ──────────────────────────────────────────────────
say "Configuring UFW firewall (allow SSH + HTTP + HTTPS only)…"
# Don't lock ourselves out — explicit allow on 22 BEFORE enable.
ufw allow 22/tcp >/dev/null
ufw allow 80/tcp >/dev/null
ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
ok "UFW enabled — only ports 22/80/443 open"

# ── Step 3: Docker ────────────────────────────────────────────────────
if command -v docker >/dev/null 2>&1; then
    ok "Docker already installed ($(docker --version | head -1))"
else
    say "Installing Docker…"
    curl -fsSL https://get.docker.com | sh
    ok "Docker installed"
fi
docker compose version >/dev/null 2>&1 || die "docker compose plugin missing"

# Make Docker auto-start at boot (already default on systemd, but explicit)
systemctl enable --now docker >/dev/null 2>&1 || true

# ── Step 4: Caddy (from official repo) ───────────────────────────────
if command -v caddy >/dev/null 2>&1; then
    ok "Caddy already installed ($(caddy version | head -1))"
else
    say "Installing Caddy from the official Cloudsmith repo…"
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
    apt-get update -qq
    apt-get install -y -qq caddy
    ok "Caddy installed"
fi

# ── Step 5: clone or update the repo ─────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
    say "Repo already at $INSTALL_DIR — pulling latest main…"
    git -C "$INSTALL_DIR" fetch origin main --quiet
    git -C "$INSTALL_DIR" reset --hard origin/main --quiet
    ok "Repo updated to $(git -C "$INSTALL_DIR" log -1 --oneline)"
else
    say "Cloning repo to $INSTALL_DIR…"
    git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    ok "Repo cloned to $INSTALL_DIR"
fi

# ── Step 6: Caddyfile from template ──────────────────────────────────
say "Rendering /etc/caddy/Caddyfile for domain '$DOMAIN'…"
sed "s/foresight\.example\.com/$DOMAIN/g" \
    "$INSTALL_DIR/scripts/deploy/Caddyfile.template" \
    > /etc/caddy/Caddyfile

# Prepare the access-log directory. The Caddyfile points its access
# log at /var/log/caddy/foresight.log; if the `caddy` system user
# can't write there, `systemctl start caddy` exits 1 with
# "permission denied" before any TLS / cert dance even runs.
# Live cutover bug 2026-05-05: the pre-fix version ran
# `chown ... 2>/dev/null || true` which silenced the failure. The
# `getent passwd caddy` guard checks the user actually exists (apt's
# caddy package creates it, but a future package layout shift would
# fail loud here instead of shipping a broken bootstrap).
mkdir -p /var/log/caddy
chmod 755 /var/log/caddy
if getent passwd caddy >/dev/null; then
    chown -R caddy:caddy /var/log/caddy
    ok "Caddy log dir owned by caddy:caddy"
else
    die "Expected 'caddy' system user is missing — apt may have installed Caddy in a non-standard layout. Aborting."
fi

caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
    || die "Generated Caddyfile is invalid — check $INSTALL_DIR/scripts/deploy/Caddyfile.template"
ok "Caddyfile written + validated"

# Note: we do NOT systemctl restart caddy here — the cert challenge
# would fail until the .env is filled and the stack is running. The
# operator restarts caddy AFTER `docker compose up -d` succeeds.

# ── Step 7: systemd unit for the docker stack ────────────────────────
say "Installing systemd unit for auto-start at reboot…"
cp "$INSTALL_DIR/scripts/deploy/foresight.service" /etc/systemd/system/foresight.service
# Patch the WorkingDirectory if INSTALL_DIR was overridden
sed -i "s|WorkingDirectory=/opt/foresight|WorkingDirectory=$INSTALL_DIR|" \
    /etc/systemd/system/foresight.service
systemctl daemon-reload
systemctl enable foresight.service >/dev/null 2>&1
ok "Systemd unit foresight.service enabled (will start at next reboot — does NOT start it now)"

# ── Step 8: backup cron ──────────────────────────────────────────────
say "Wiring daily Postgres backup at 03:00 UTC…"
cp "$INSTALL_DIR/scripts/deploy/backup-postgres.sh" /usr/local/bin/foresight-backup
chmod +x /usr/local/bin/foresight-backup
mkdir -p "$BACKUP_DIR"
# Idempotent: only add if not already in crontab
if ! crontab -l 2>/dev/null | grep -q "foresight-backup"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/foresight-backup") | crontab -
fi
ok "Backup cron registered (target: $BACKUP_DIR/, retention: 14 days)"

# ── Step 9: .env stub ────────────────────────────────────────────────
if [ -f "$INSTALL_DIR/.env" ]; then
    warn ".env already exists at $INSTALL_DIR/.env — leaving it alone"
else
    say "Copying production.env.template → $INSTALL_DIR/.env (you'll fill it next)"
    cp "$INSTALL_DIR/scripts/deploy/production.env.template" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
    ok ".env stub created (chmod 600 — only root can read)"
fi

# ── Done ──────────────────────────────────────────────────────────────
cat <<EOF

${GREEN}═══════════════════════════════════════════════════════════════════════${NC}
  Bootstrap complete. Box is ready for secrets + boot.
${GREEN}═══════════════════════════════════════════════════════════════════════${NC}

NEXT STEPS — do these in order:

  ${BLUE}1.${NC} Fill the secrets in $INSTALL_DIR/.env

       nano $INSTALL_DIR/.env

     Generators (run on this server):
       openssl rand -hex 32   # JWT_SECRET_KEY, TELEGRAM_WEBHOOK_SECRET
       openssl rand -hex 24   # POSTGRES_PASSWORD

  ${BLUE}2.${NC} Validate that nothing default leaked through:

       bash $INSTALL_DIR/scripts/deploy/preflight-check.sh

     The check is in $INSTALL_DIR/.env mode — \`ENV=production\` plus
     non-default JWT, DB password, Telegram secret. ${RED}Do NOT proceed${NC}
     until it prints ${GREEN}"All checks passed"${NC}.

  ${BLUE}3.${NC} Boot the stack:

       cd $INSTALL_DIR && docker compose up -d

  ${BLUE}4.${NC} Restart Caddy (now that the upstream containers are reachable):

       systemctl restart caddy
       systemctl status caddy --no-pager | head

     Caddy will request the Let's Encrypt cert for $DOMAIN on the
     first HTTPS request. DNS for $DOMAIN must already point to this
     server (A record).

  ${BLUE}5.${NC} Smoke test from your laptop:

       curl https://$DOMAIN/api/health
       open https://$DOMAIN

EOF
