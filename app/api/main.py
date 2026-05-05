"""FastAPI application — single entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings, log_active_config
from app.db.database import engine

logger = logging.getLogger(__name__)
settings = get_settings()


_INSECURE_JWT_SECRET_DEFAULTS = {
    "change-me-in-production",
    "foresight-dev-secret-key-change-in-prod-2026",
    "",
}


def _assert_jwt_secret_safe_for_env() -> None:
    """Refuse to boot in production when JWT_SECRET_KEY is a known
    default. Pre-fix (P0-4 audit, 2026-04-27), the source-code default
    `change-me-in-production` was silently used if the env var was
    absent — meaning any token signed with that public string was
    valid against any deployment that forgot to override it.
    Dev/test envs continue to allow defaults so local stacks boot
    without ceremony.
    """
    if settings.env != "production":
        return
    if settings.jwt_secret_key in _INSECURE_JWT_SECRET_DEFAULTS:
        raise RuntimeError(
            "JWT_SECRET_KEY is set to a known default in production. "
            "Set a strong, unique value via the JWT_SECRET_KEY env var "
            "before booting (e.g. `openssl rand -hex 32`)."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is owned by Alembic — `alembic upgrade head` runs in the
    # Docker entrypoint before uvicorn boots. Audit follow-up: previous
    # in-lifespan auto-table-init raced concurrent boots and silently
    # masked drift between SQLAlchemy models and migration state.
    _assert_jwt_secret_safe_for_env()
    # Surface every silent-effect flag at boot — see the docstring of
    # `log_active_config` for the rationale (the 2026-05-05 OOM that
    # `echo=settings.is_development` silently caused).
    log_active_config(logger)
    logger.info("Foresight API started")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Prediction Markets Intelligence Platform",
    version=settings.app_version,
    lifespan=lifespan,
)

from app.api.cors import resolve_cors_origins  # noqa: E402

# Audit follow-up: explicit allow-list per env. Wildcard + credentials is
# rejected by browsers AND a CSRF surface; prod is locked to the public
# origin (+ optional staging/apex via cors_extra_origins).
_cors_extras = [o.strip() for o in (settings.cors_extra_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=resolve_cors_origins(
        env=settings.env,
        app_base_url=settings.app_base_url,
        extra_origins=_cors_extras,
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.middleware import ApiKeyMiddleware, RateLimitMiddleware  # noqa: E402

app.add_middleware(RateLimitMiddleware)
app.add_middleware(ApiKeyMiddleware)

from app.api.routes import router  # noqa: E402

app.include_router(router, prefix="/api")

from app.api.websocket import router as ws_router  # noqa: E402

app.include_router(ws_router)

from app.api.push import router as push_router  # noqa: E402

app.include_router(push_router, prefix="/api")

from app.api.routes.admin_metrics import router as admin_metrics_router  # noqa: E402
from app.api.routes.agents import router as agents_router  # noqa: E402
from app.api.routes.api_keys import router as api_keys_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.outcome_views import router as outcome_views_router  # noqa: E402
from app.api.routes.paper import router as paper_router  # noqa: E402
from app.api.routes.performance_v2 import router as performance_v2_router  # noqa: E402
from app.api.routes.portfolio_v2 import router as portfolio_v2_router  # noqa: E402
from app.api.routes.public_stats import router as public_stats_router  # noqa: E402
from app.api.routes.quota import router as quota_router  # noqa: E402
from app.api.routes.sources import router as sources_router  # noqa: E402
from app.api.routes.subscriptions import router as subs_router  # noqa: E402
from app.api.routes.trading import router as trading_router  # noqa: E402
from app.api.routes.trading_wallet import router as trading_wallet_router  # noqa: E402

app.include_router(trading_router, prefix="/api")
app.include_router(trading_wallet_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(api_keys_router, prefix="/api")
app.include_router(subs_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(portfolio_v2_router, prefix="/api")
app.include_router(performance_v2_router, prefix="/api")
app.include_router(quota_router, prefix="/api")
app.include_router(public_stats_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
# `paper` keeps its bac-à-sable role inside Apprendre — no real-money
# implications. The L&T trading-test gates (the former /api/onboarding/*
# and /api/quiz/* route files) were removed in the 2026-04-27 P0 audit
# cleanup once we confirmed nothing else (CI, scheduled jobs, telemetry)
# consumed them.
app.include_router(paper_router, prefix="/api")
app.include_router(outcome_views_router, prefix="/api")
app.include_router(admin_metrics_router, prefix="/api")

from app.api.routes.b2b import router as b2b_router  # noqa: E402

app.include_router(b2b_router, prefix="/api")

from app.api.routes.telegram_webhook import router as tg_webhook_router  # noqa: E402

app.include_router(tg_webhook_router, prefix="/api")


@app.get("/.well-known/apple-developer-merchantid-domain-association")
async def apple_pay_domain_verification():
    """Serve Apple Pay domain verification file for Stripe."""
    import pathlib

    from fastapi.responses import PlainTextResponse

    path = pathlib.Path(__file__).parent.parent.parent / "static" / "apple-developer-merchantid-domain-association"
    if path.exists():
        return PlainTextResponse(path.read_text())
    return PlainTextResponse("", status_code=404)
