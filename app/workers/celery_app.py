"""Celery application — broker config + beat schedule.

Queue architecture (post-2026-04-27 P1-9 split):
  ingestion         → RSS/API fetch, X-scraper inbox
  pipeline          → process_article, batch embed backfill, batch build_events backfill
  scoring           → try_instant_event, hybrid search + LLM + signal (REALTIME hot path)
  scoring_recovery  → retry_stuck_events, rescore_zero_signal_events, backfill_reasoning
  sourcing          → tasks_sourcing.* (shadow re-runs, can lag without hurting prod)
  embeddings        → tasks_embeddings_backfill.* (batch jobs)
  ranking_shadow    → tasks_ranking_shadow.* (analytical, fire-and-forget)
  markets           → fetch_markets, percentiles (heavy, isolated)
  trading           → position sync, risk monitoring, daily briefs
  default           → outcome tracking

Pre-split, the `scoring` queue carried realtime + sourcing + embeddings
+ ranking_shadow + recovery sweeps. A heavy backfill or shadow re-run
would HOL-block live signal generation. Each subordinate path is now
on its own queue and the realtime worker (`worker-scoring`) only
consumes `scoring` — see docker-compose.yml `worker-scoring-batch` for
the dedicated worker that drains the four batch queues.
"""

import logging
import os

from celery import Celery
from celery.signals import task_postrun, worker_ready

from app.core.config import get_settings, log_active_config
from app.core.sentry_init import init_sentry

logger = logging.getLogger(__name__)
settings = get_settings()

# Sentry init has to happen before any task can run so the
# CeleryIntegration auto-wires up its task-execution hooks. Like the
# API side, this is a silent no-op when SENTRY_DSN is unset.
init_sentry(component="celery")


# ── Worker recycling (memory leak mitigation) ──────────────────────────
# Celery `--pool=solo` does not support `worker_max_tasks_per_child`
# (that flag is prefork-only). We get the same effect by hand: count
# completed tasks per worker and `os._exit(0)` when the threshold is
# reached. Docker `restart: unless-stopped` brings the worker back in
# ~5 s, and the new process starts with a clean RSS.
#
# Why this is needed even with NullPool (PR #40) + 3 GB ceiling (PR #41):
# Python+spaCy+SQLAlchemy in a long-running asyncio process slowly
# accumulates objects (Doc cache, ORM identity map, asyncio task
# bookkeeping). NullPool stopped the asyncpg leak; the residual creep
# was measured at ~+60 MB / 10 min on worker-pipeline-1, which is fine
# at 3 GB ceiling for ~5 hours but not "indefinitely fine". 100 tasks
# = ~30-50 min between recycles in our throughput band, comfortably
# below where the residual growth becomes a problem. Configurable via
# `CELERY_WORKER_MAX_TASKS` env var; set to 0 to disable.
_TASK_COUNTER: dict[str, int] = {"completed": 0}
_WORKER_MAX_TASKS = int(os.environ.get("CELERY_WORKER_MAX_TASKS", "100"))


@worker_ready.connect
def _log_active_config_on_worker_ready(sender=None, **kwargs):
    """Dump the silent-effect config flags once the worker is up.

    Mirrors what FastAPI does in `lifespan`. Each long-lived process
    surfaces its active config to its own logger so an operator can see
    e.g. `db_echo=True` *before* the worker starts processing tasks and
    OOMs from log buffer pressure (the 2026-05-05 incident).
    """
    log_active_config(logger)


@task_postrun.connect
def _recycle_worker_after_n_tasks(sender=None, task_id=None, **kwargs):
    """Exit cleanly after N tasks so Docker can revive a fresh worker.

    Fires after the task's result is acked to Celery, so we never
    interrupt mid-task. `os._exit(0)` is intentional: a graceful Celery
    shutdown via `sys.exit` would stall waiting for in-flight workers
    that don't exist (we're solo) and add latency. Hard exit + Docker
    restart is the most direct path back to a clean RSS.
    """
    if _WORKER_MAX_TASKS <= 0:
        return  # disabled
    _TASK_COUNTER["completed"] += 1
    if _TASK_COUNTER["completed"] >= _WORKER_MAX_TASKS:
        logger.info(
            "Worker recycle threshold reached (%d tasks). Exiting for fresh restart.",
            _WORKER_MAX_TASKS,
        )
        os._exit(0)

celery_app = Celery(
    "signal",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Bumped from 300/240 to 600/540 on 2026-05-04 after a 6-day outage
    # where all 8 workers crashed in a 5-minute restart loop. Root cause:
    # a `process_article` task occasionally hangs >300s on a slow
    # OpenAI embedding or RSSHub call (no per-call timeout in the
    # caller). At 300s hard-limit Celery force-kills the worker via
    # SIGKILL, the next task from the backlog reproduces the issue, and
    # the loop never breaks. 600s gives enough breathing room for the
    # tail of network-bound calls; the actual fix (per-call timeouts in
    # the embedding service + httpx clients) lands separately so the
    # bump remains in place as a safety margin.
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

celery_app.conf.task_routes = {
    "app.workers.tasks_ingestion.fetch_markets": {"queue": "markets"},
    "app.workers.tasks_ingestion.compute_market_percentiles": {"queue": "markets"},
    "app.workers.tasks_ingestion.*": {"queue": "ingestion"},
    "app.workers.tasks_pipeline.try_instant_event": {"queue": "scoring"},
    "app.workers.tasks_pipeline.*": {"queue": "pipeline"},
    # P1-9: keep `scoring` queue for the realtime hot path only. Recovery
    # sweeps move to `scoring_recovery` so a backfill burst cannot push
    # live signal generation behind it. Most-specific routes first — Celery
    # picks the first matching pattern.
    "app.workers.tasks_scoring.retry_stuck_events": {"queue": "scoring_recovery"},
    "app.workers.tasks_scoring.rescore_zero_signal_events": {"queue": "scoring_recovery"},
    "app.workers.tasks_scoring.backfill_reasoning": {"queue": "scoring_recovery"},
    "app.workers.tasks_scoring.*": {"queue": "scoring"},
    "app.workers.tasks_sourcing.*": {"queue": "sourcing"},
    "app.workers.tasks_outcomes.*": {"queue": "default"},
    "app.workers.tasks_trading.*": {"queue": "trading"},
    "app.workers.tasks_risk.*": {"queue": "trading"},
    "app.workers.tasks_reports.*": {"queue": "trading"},
    "app.workers.tasks_embeddings_backfill.*": {"queue": "embeddings"},
    "app.workers.tasks_ranking_shadow.*": {"queue": "ranking_shadow"},
}

_beat_schedule = {
    # ── Ingestion — RSS tier-1 (wire sources) at fast cadence ──────
    # Reuters, AFP, AP, BBCBreaking, FirstSquawk, business etc. — the
    # latency-critical accounts. Polls every
    # `tier1_rss_poll_interval_seconds` (default 15 s) to stay near
    # RSSHub's 60 s cache TTL floor.
    "fetch-rss-tier1-fast": {
        "task": "app.workers.tasks_ingestion.fetch_rss_tier1",
        "schedule": settings.tier1_rss_poll_interval_seconds,
        "options": {"queue": "ingestion"},
    },
    # ── Ingestion — RSS tier-2/3 at slow cadence ────────────────────
    # Commentary feeds, secondary X accounts, World News API. Polled
    # every `rss_poll_interval_seconds` (default 90 s).
    "fetch-rss-tier-low": {
        "task": "app.workers.tasks_ingestion.fetch_rss_feeds",
        "schedule": settings.rss_poll_interval_seconds,
        "options": {"queue": "ingestion"},
    },
    # ── Ingestion — World News API ───────────────────────────────────
    # Disabled 2026-05-10: fetched=50 inserted=0 sur 7+ jours (toutes les
    # rows déjà connues → max_age_hours=2 + dedupe URL les rejettent toutes).
    # World News API + 14 country codes WorldNews:* sont actifs en DB mais
    # produisent 0 rows depuis ≥7j. La task spamme worker-ingestion sans gain.
    # Pour réactiver : décommenter ci-dessous + audit pourquoi inserted=0.
    # "fetch-worldnews": {
    #     "task": "app.workers.tasks_ingestion.fetch_worldnews",
    #     "schedule": settings.worldnews_poll_interval_seconds,
    #     "options": {"queue": "ingestion"},
    # },
    # ── Ingestion — Telegram channels (FirstSquawk etc.) ─────────────
    # No-op if TELEGRAM_API_ID/HASH/SESSION_STRING are not set in .env.
    # See app/scripts/init_telegram_session.py for one-shot setup.
    "fetch-telegram-channels": {
        "task": "app.workers.tasks_ingestion.fetch_telegram_channels",
        "schedule": settings.telegram_poll_interval_seconds,
        "options": {"queue": "ingestion"},
    },
    # ── Markets — isolated queue ─────────────────────────────────────
    "fetch-markets": {
        "task": "app.workers.tasks_ingestion.fetch_markets",
        "schedule": settings.market_refresh_interval_seconds,
        "options": {"queue": "markets"},
    },
    "compute-market-percentiles": {
        "task": "app.workers.tasks_ingestion.compute_market_percentiles",
        "schedule": settings.market_percentile_interval_seconds,
        "options": {"queue": "markets"},
    },
    # ── Backfill — batch embedding (stragglers only) ─────────────────
    "embed-news-batch": {
        "task": "app.workers.tasks_pipeline.compute_embedding_batch",
        "schedule": settings.embedding_batch_interval_seconds,
        "options": {"queue": "pipeline"},
    },
    # ── Backfill — periodic event sweep (catches fast-path misses) ───
    "build-events": {
        "task": "app.workers.tasks_pipeline.build_events",
        "schedule": settings.build_events_interval_seconds,
        "options": {"queue": "pipeline"},
    },
    # ── Recovery — retry stuck events (off the realtime queue, P1-9) ──
    "retry-stuck-events": {
        "task": "app.workers.tasks_scoring.retry_stuck_events",
        "schedule": 300,
        "options": {"queue": "scoring_recovery"},
    },
    # ── Recovery — re-score events with 0 signals (off the realtime queue, P1-9) ──
    "rescore-zero-signals": {
        "task": "app.workers.tasks_scoring.rescore_zero_signal_events",
        "schedule": 600,
        "options": {"queue": "scoring_recovery"},
    },
    # ── Ingestion — GDELT 2.0 ────────────────────────────────────────────────
    "fetch-gdelt-every-5min": {
        "task": "app.workers.tasks_ingestion.fetch_gdelt",
        "schedule": 300.0,
        "options": {"queue": "ingestion"},
    },
    # ── Outcomes — backfill missing prices ────────────────────────────
    "catchup-outcomes": {
        "task": "app.workers.tasks_outcomes.catchup_outcomes",
        "schedule": 600,
        "options": {"queue": "default"},
    },
    # ── Outcomes — check resolved markets (every 6h) ─────────────────
    "check-resolved-markets": {
        "task": "app.workers.tasks_outcomes.check_resolved_markets",
        "schedule": 6 * 3600,
        "options": {"queue": "default"},
    },
}

if settings.x_scraper_inbox_interval_seconds > 0:
    _beat_schedule["ingest-x-scraper-inbox"] = {
        "task": "app.workers.tasks_ingestion.ingest_x_scraper_inbox",
        "schedule": settings.x_scraper_inbox_interval_seconds,
        "options": {"queue": "ingestion"},
    }

_beat_schedule["poll-order-fills"] = {
    "task": "app.workers.tasks_trading.poll_order_fills",
    "schedule": 60,
    "options": {"queue": "trading"},
}
_beat_schedule["sync-positions"] = {
    "task": "app.workers.tasks_trading.sync_positions",
    "schedule": 300,
    "options": {"queue": "trading"},
}
_beat_schedule["monitor-risk"] = {
    "task": "app.workers.tasks_risk.monitor_positions",
    "schedule": 300,
    "options": {"queue": "trading"},
}
_beat_schedule["daily-brief"] = {
    "task": "app.workers.tasks_reports.generate_daily_brief",
    "schedule": 86400,
    "options": {"queue": "trading"},
}

# ── Observability — clustering-diversity histogram (chantier-2) ──
_beat_schedule["clustering-diversity-hourly"] = {
    "task": "app.workers.tasks_diagnostics.emit_diversity_distribution",
    "schedule": 3600.0,
    "options": {"queue": "default"},
}

# ── Observability — daily bucket × direction × outcome roll-up ──
# Audit follow-up 2026-04-28: 27-04 retro surfaced that geopolitics×BUY_NO
# was the dominant loss vector. Hourly is overkill (at most a few tens of
# signals/hour) but daily is enough cadence to spot a regime change in
# bucket performance without spamming the logs.
_beat_schedule["signals-outcome-daily"] = {
    "task": "app.workers.tasks_diagnostics.emit_signals_outcome_distribution",
    "schedule": 86400.0,
    "options": {"queue": "default"},
}

# ── Retention — nightly DELETE of stale rows from growing tables ──
# Without this, llm_cost_log alone grows ~370k rows/month and the
# event_market_candidates / ranking_shadow tables would push the DB
# past 50 GB inside 6 months. Per-table caps keep the per-run lock
# window short — see app/workers/tasks_retention.py for policy detail.
_beat_schedule["retention-nightly"] = {
    "task": "app.workers.tasks_retention.run_retention",
    "schedule": 86400.0,
    "options": {"queue": "default"},
}

# ── Observability — OpenAI cost watch (T-008) ─────────────────────────
# Daily 24 h roll-up of llm_cost_log grouped by (call_type, model).
# Same cadence as retention-nightly but offset so they don't run on the
# same beat tick (the cost task is read-only and tiny — single grouped
# SELECT — but no reason to bunch them). Fires a Telegram alert when
# 24 h spend crosses 50 % of `llm_cost_alert_usd` so an operator gets
# a leading indicator before the circuit breaker drops live signals.
_beat_schedule["cost-watch-daily"] = {
    "task": "app.workers.tasks_costs.emit_daily_cost",
    "schedule": 86400.0,
    "options": {"queue": "default"},
}

celery_app.conf.beat_schedule = _beat_schedule

celery_app.autodiscover_tasks([
    "app.workers.tasks_ingestion",
    "app.workers.tasks_pipeline",
    "app.workers.tasks_scoring",
    "app.workers.tasks_sourcing",
    "app.workers.tasks_outcomes",
    "app.workers.tasks_trading",
    "app.workers.tasks_risk",
    "app.workers.tasks_reports",
    "app.workers.tasks_embeddings_backfill",
    "app.workers.tasks_ranking_shadow",
    "app.workers.tasks_diagnostics",
    "app.workers.tasks_retention",
    "app.workers.tasks_costs",
])


# ── Worker-only tasks (telethon) ──────────────────────────────────────
# `tasks_telegram_admin` imports telethon, which is only installed on
# the `worker-ingestion` image. The `app` API container would crash at
# import if we let autodiscovery try to load it there. Import it
# inside a guarded block so workers register the tasks while the API
# stays clean. The API dispatches via `celery_app.send_task(...)` by
# name, which does NOT require the task object to be importable in the
# caller process.
try:
    import app.workers.tasks_telegram_admin  # noqa: F401
except ImportError as _e:
    logger.info("tasks_telegram_admin not loaded (likely missing telethon — expected on `app` container): %s", _e)
