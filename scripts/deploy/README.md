# Production deploy runbook

Last updated 2026-05-05.

This is the step-by-step playbook to take Foresight from "runs on my Mac
when Docker Desktop is open" to "runs 24/7 on a VPS with a public domain
and TLS." It assumes:

- A target VPS — Hetzner CPX31 / DigitalOcean 4 GB / Linode 4 GB equivalent
  is the sweet spot. Anything ≥ 4 GB RAM and 2 vCPU works.
- Ubuntu 22.04 or 24.04 LTS as the host OS.
- A domain you control (Cloudflare, Namecheap, OVH — any registrar).
- SSH access via a public key (no password auth — the VPS will reject it).

The ordering matters. Don't skip the **pre-flight** even if you're in a
hurry: shipping with the dev-default JWT secret to a public URL turns
the API into a forge-able token factory (see audit M5 / PR #54).

---

## 0. Pre-deploy housekeeping (do BEFORE creating the VPS)

```bash
# Rotate every credential that was in `.env.backup-2026-04-27`
# (audit follow-up — these are considered exposed).
#   * OpenAI:  https://platform.openai.com/api-keys
#   * WorldNews: https://worldnewsapi.com/console/
#   * X / Twitter: log into your burner account, copy fresh cookies
#     from the browser dev tools (auth_token, ct0). Runbook in
#     docs/setup-rsshub-twitter.md.

# Generate strong secrets. Save them in your password manager NOW —
# you will need them in step 2.
JWT_SECRET=$(openssl rand -hex 32)               # 64 hex chars
TELEGRAM_WEBHOOK_SECRET=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 24)              # 48 hex chars
echo "JWT_SECRET=$JWT_SECRET"
echo "TELEGRAM_WEBHOOK_SECRET=$TELEGRAM_WEBHOOK_SECRET"
echo "DB_PASSWORD=$DB_PASSWORD"
```

---

## 1. Provision the VPS

Hetzner Cloud is the cheapest credible option (~€13/mo for CPX31). Pick
one image, one region, and SSH-key auth. No password auth.

```bash
# After provisioning, from your laptop:
ssh root@<vps-ip>

# Replace `root` with `ubuntu` if your provider's image uses it.
```

### Fast path — `setup.sh` one-liner

The bootstrap (system update, UFW, Docker, Caddy install, repo clone,
Caddyfile rendered with your domain, systemd unit, backup cron, `.env`
stub) is automated. From inside the VPS:

```bash
# Default domain is yourforesight.com — override with DOMAIN= if different
curl -fsSL https://raw.githubusercontent.com/vcapton-jpg/polymarket-ai/main/scripts/deploy/setup.sh | bash

# Or with a custom domain:
DOMAIN=foresight.example.com curl -fsSL ... | DOMAIN=foresight.example.com bash
```

What this does NOT do (operator must, after):
1. Fill `/opt/foresight/.env` with rotated secrets — `nano /opt/foresight/.env`
2. Run `bash /opt/foresight/scripts/deploy/preflight-check.sh` — must pass green
3. `cd /opt/foresight && docker compose up -d`
4. `systemctl restart caddy` once the stack is up

### Slow path — manual (if the script fails or you want to read each step)

```bash
apt-get update && apt-get upgrade -y
apt-get install -y ufw
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable
curl -fsSL https://get.docker.com | sh
docker --version && docker compose version
```

---

## 2. Pull the repo and configure

```bash
cd /opt
git clone https://github.com/vcapton-jpg/polymarket-ai.git foresight
cd foresight

# Copy the production env template
cp scripts/deploy/production.env.template .env
nano .env
```

Fill in every `REQUIRED:` value. The file is heavily commented — every
secret has a short note about what fails if it's missing. **Use the
secrets from step 0** (don't reuse dev defaults).

Then run the pre-flight check before booting:

```bash
bash scripts/deploy/preflight-check.sh
```

The script exits non-zero if anything is wrong (default JWT, missing
Telegram secret in production, weak DB password, etc.). Don't proceed
until it returns "All checks passed."

---

## 3. Reverse proxy + TLS

```bash
# Install Caddy — does Let's Encrypt certs automatically
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update && apt-get install -y caddy

# Copy the Caddy config template
cp scripts/deploy/Caddyfile.template /etc/caddy/Caddyfile
nano /etc/caddy/Caddyfile  # replace foresight.example.com with your domain

systemctl restart caddy
systemctl enable caddy
```

Point your domain's `A` record to the VPS IP. DNS propagation is
usually < 5 min. Caddy will request the TLS certificate automatically
on the first request.

---

## 4. Boot the stack

```bash
cd /opt/foresight
docker compose up -d

# Wait for healthchecks
docker compose ps
docker compose logs -f --tail 50 app worker-pipeline-1 worker-scoring
```

Look for the `===== Foresight active config =====` block in each
container's logs (PR #47). Confirm `db_echo=False`, `env=production`,
`jwt_secret_key=set`, `telegram_webhook_secret=set`.

---

## 5. Auto-restart on reboot

```bash
cp scripts/deploy/foresight.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable foresight
# `systemctl start foresight` is a no-op since docker compose already
# brought everything up; the unit only matters at next reboot.
```

---

## 6. Daily Postgres backup

```bash
mkdir -p /var/backups/foresight
cp scripts/deploy/backup-postgres.sh /usr/local/bin/foresight-backup
chmod +x /usr/local/bin/foresight-backup

# Cron: daily at 03:00 UTC, 14-day retention is in the script
echo "0 3 * * * /usr/local/bin/foresight-backup" | crontab -

# Smoke-test
/usr/local/bin/foresight-backup
ls -lh /var/backups/foresight/
```

For real durability: rsync `/var/backups/foresight/` to a Backblaze B2
or S3 bucket (out of scope for this runbook — see `docs/runbooks/`
when it exists).

---

## 7. Register the Telegram webhook

```bash
TELEGRAM_BOT_TOKEN=$(grep ^TELEGRAM_BOT_TOKEN .env | cut -d= -f2)
TELEGRAM_WEBHOOK_SECRET=$(grep ^TELEGRAM_WEBHOOK_SECRET .env | cut -d= -f2)
DOMAIN=foresight.example.com  # your domain

curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
  -d "url=https://${DOMAIN}/api/telegram/webhook" \
  -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"

# Verify
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
```

The webhook secret travels in the `X-Telegram-Bot-Api-Secret-Token` header
on every Telegram delivery. PR #45's handler refuses everything else with
401, so a probe can't spoof updates.

---

## 8. Monitoring

Two free tools that pay for themselves the first time prod is silently
broken:

- **UptimeRobot** — sign up, add an HTTP monitor on `https://<domain>/api/health`
  with 5-minute interval. Email alerts on DOWN.
- **Sentry** — sign up, create a Python project, drop the DSN into `.env`
  as `SENTRY_DSN=...`. (Backend wiring lives at follow-up scope today.)

---

## 9. Operational runbook

```bash
# Pull latest code
cd /opt/foresight
git pull origin main
docker compose up -d --build  # rebuild only what changed

# Tail logs
docker compose logs -f --tail 100 worker-pipeline-1

# Apply a migration
docker compose exec app alembic upgrade head

# DB shell (read-only friendly, careful with writes)
docker compose exec db psql -U postgres signal

# Restart everything cleanly
docker compose restart

# Hard rebuild (rarely needed)
docker compose down && docker compose up -d --build
```

---

## 10. Cutover from local dev

Run BOTH stacks for 48 hours:

- Your Mac stack on `localhost:3000`
- Prod stack on `https://foresight.example.com`

Compare:
- Signal counts per hour (should be similar; prod might be slightly
  ahead on uptime).
- DB row counts on `news`, `events`, `signals`.
- LLM cost rate (should be ~equal — both stacks compete for the same
  data sources).

Once they agree for 2 days, kill the Mac stack:

```bash
# On your Mac
docker compose down
```

Now your laptop can sleep, fly, drown, whatever — the prod pipeline
keeps running.

---

## Cost estimate

| Line item | Monthly | One-off |
|-----------|---------|---------|
| Hetzner CPX31 (4 vCPU / 8 GB / 160 GB) | €13 | — |
| Domain (.com from Cloudflare) | — | €8/year |
| Cloudflare DNS + email forward | — | €0 |
| Backblaze B2 (10 GB backups) | $0.06 | — |
| UptimeRobot free tier | $0 | — |
| Sentry free tier | $0 | — |
| **Total** | **~€14/mo** | **~€8/year** |

Plus your existing OpenAI / WorldNews / Polymarket spend, which is the
same on dev and prod.

---

## What NOT to do

- **Don't** put the VPS IP into the frontend `VITE_API_BASE_URL` and skip
  the domain. Without TLS, browsers refuse the WebSocket and you'll
  spend hours debugging "API works but realtime is broken."
- **Don't** open port 5432 (Postgres) or 6379 (Redis) on the VPS firewall.
  PR #39 already binds them to 127.0.0.1 in `docker-compose.yml`, but
  if you accidentally undo that, UFW is the last line.
- **Don't** commit the production `.env` to git. The repo's `.gitignore`
  blocks it (PR #45) but `git add -A` accidents are how leaks happen —
  always `git status` before committing.
- **Don't** use `docker compose down` to deploy. It stops every
  container including the DB. Use `docker compose up -d --build` which
  recreates only services with changed images and leaves the DB alone.
