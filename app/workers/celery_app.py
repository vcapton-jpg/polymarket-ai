"""Celery application — broker config + beat schedule.

Queue architecture:
  ingestion  → RSS/API fetch, X-scraper inbox
  pipeline   → process_article, batch embed backfill, batch build_events backfill
  scoring    → try_instant_event, hybrid search + LLM + signal (fast path)
  markets    → fetch_markets, percentiles (heavy, isolated)
  trading    → position sync, risk monitoring, daily briefs
  default    → outcome tracking
"""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

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
    task_time_limit=300,
    task_soft_time_limit=240,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

celery_app.conf.task_routes = {
    "app.workers.tasks_ingestion.fetch_markets": {"queue": "markets"},
    "app.workers.tasks_ingestion.compute_market_percentiles": {"queue": "markets"},
    "app.workers.tasks_ingestion.*": {"queue": "ingestion"},
    "app.workers.tasks_pipeline.try_instant_event": {"queue": "scoring"},
    "app.workers.tasks_pipeline.*": {"queue": "pipeline"},
    "app.workers.tasks_scoring.*": {"queue": "scoring"},
    "app.workers.tasks_outcomes.*": {"queue": "default"},
    "app.workers.tasks_trading.*": {"queue": "trading"},
    "app.workers.tasks_risk.*": {"queue": "trading"},
    "app.workers.tasks_reports.*": {"queue": "trading"},
}

_beat_schedule = {
    # ── Ingestion — RSS feeds ────────────────────────────────────────
    "fetch-rss-tier1": {
        "task": "app.workers.tasks_ingestion.fetch_rss_feeds",
        "schedule": settings.rss_poll_interval_seconds,
        "options": {"queue": "ingestion"},
    },
    # ── Ingestion — World News API ───────────────────────────────────
    "fetch-worldnews": {
        "task": "app.workers.tasks_ingestion.fetch_worldnews",
        "schedule": settings.worldnews_poll_interval_seconds,
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
        "options": {"queue": "scoring"},
    },
    # ── Recovery — retry stuck events ────────────────────────────────
    "retry-stuck-events": {
        "task": "app.workers.tasks_scoring.retry_stuck_events",
        "schedule": 300,
        "options": {"queue": "scoring"},
    },
    # ── Recovery — re-score events with 0 signals ──────────────────
    "rescore-zero-signals": {
        "task": "app.workers.tasks_scoring.rescore_zero_signal_events",
        "schedule": 600,
        "options": {"queue": "scoring"},
    },
    # ── Recovery — drain signals_pending_reasoning (LLM backfill) ──
    "backfill-reasoning-every-10min": {
        "task": "app.workers.tasks_scoring.backfill_reasoning",
        "schedule": 600.0,
        "options": {"queue": "scoring"},
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

celery_app.conf.beat_schedule = _beat_schedule

celery_app.autodiscover_tasks([
    "app.workers.tasks_ingestion",
    "app.workers.tasks_pipeline",
    "app.workers.tasks_scoring",
    "app.workers.tasks_outcomes",
    "app.workers.tasks_trading",
    "app.workers.tasks_risk",
    "app.workers.tasks_reports",
])
