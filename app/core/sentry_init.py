"""Sentry SDK bootstrap — shared by FastAPI + Celery.

T-006 in docs/PLAN_30D_SIGNAL_QUALITY.md. The plan tracker calls out
observability as the prerequisite for measuring whether Sprint 1
filters (T-001 BUY_NO×price, T-007 toxic sources) actually move RTP:
without an error pipeline, the first 30-day signal-quality sprint
operates blind on production crashes.

Two integration goals:
  * FastAPI — catch every uncaught route exception with request context
    (path, method, headers, user.id via auth dep). Trace 5 % of
    requests so we can compare endpoint latency without paying for
    full transactions.
  * Celery — task-level breadcrumbs + auto-capture of failed tasks. A
    backfill that silently retries 47 times today would surface as 47
    errors with the same fingerprint.

`init_sentry()` is a no-op when `sentry_dsn` is unset → `pytest`,
local dev, and CI never need the project. Calling it twice in the
same process is safe (sentry_sdk.init is idempotent).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SENTRY_INITIALIZED = False


def init_sentry(component: str) -> bool:
    """Initialize Sentry for the given component ('api' or 'celery').

    Returns True if initialization succeeded, False if skipped (no DSN
    configured or sentry-sdk not installed).

    `component` is added as a tag so the Sentry UI can split errors by
    container without us having to grep stack traces.
    """
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning("sentry_sdk not installed — Sentry init skipped")
        return False

    from app.core.config import get_settings

    settings = get_settings()
    dsn = settings.sentry_dsn
    if not dsn:
        # Quiet by design — every dev / CI / test run hits this path.
        return False

    integrations = [
        SqlalchemyIntegration(),
    ]
    if component == "api":
        # FastAPI integration wires up Starlette internally, but pinning
        # the StarletteIntegration explicitly silences the runtime warning
        # and lets us own the `transaction_style="endpoint"` setting
        # (route function name → cleaner Sentry transaction names than
        # the raw URL with path params).
        integrations.append(StarletteIntegration(transaction_style="endpoint"))
        integrations.append(FastApiIntegration(transaction_style="endpoint"))
    elif component == "celery":
        integrations.append(
            # propagate_traces=False stops Sentry from chaining traces
            # across .delay() boundaries — task crashes show up as their
            # own root events instead of getting buried as children of
            # the API request that scheduled them.
            CeleryIntegration(monitor_beat_tasks=True, propagate_traces=False)
        )

    sentry_sdk.init(
        dsn=dsn,
        environment=settings.sentry_environment or settings.env,
        release=settings.sentry_release,
        traces_sample_rate=float(settings.sentry_traces_sample_rate),
        send_default_pii=False,  # never ship user emails/IDs to Sentry
        integrations=integrations,
    )
    sentry_sdk.set_tag("component", component)

    _SENTRY_INITIALIZED = True
    logger.info(
        "sentry: initialized component=%s env=%s sample_rate=%.3f",
        component,
        settings.sentry_environment or settings.env,
        float(settings.sentry_traces_sample_rate),
    )
    return True
