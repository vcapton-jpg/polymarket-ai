"""FastAPI application — single entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.database import engine
from app.db.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Foresight API started — tables ready")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    description="Prediction Markets Intelligence Platform",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

from app.api.routes.trading import router as trading_router  # noqa: E402
from app.api.routes.trading_wallet import router as trading_wallet_router  # noqa: E402
from app.api.routes.agents import router as agents_router  # noqa: E402
from app.api.routes.api_keys import router as api_keys_router  # noqa: E402
from app.api.routes.subscriptions import router as subs_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402
from app.api.routes.portfolio_v2 import router as portfolio_v2_router  # noqa: E402
from app.api.routes.performance_v2 import router as performance_v2_router  # noqa: E402
from app.api.routes.quota import router as quota_router  # noqa: E402
from app.api.routes.sources import router as sources_router  # noqa: E402
from app.api.routes.paper import router as paper_router  # noqa: E402
from app.api.routes.outcome_views import router as outcome_views_router  # noqa: E402
from app.api.routes.admin_metrics import router as admin_metrics_router  # noqa: E402

app.include_router(trading_router, prefix="/api")
app.include_router(trading_wallet_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(api_keys_router, prefix="/api")
app.include_router(subs_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(portfolio_v2_router, prefix="/api")
app.include_router(performance_v2_router, prefix="/api")
app.include_router(quota_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
# `paper` keeps its bac-à-sable role inside Apprendre — no real-money
# implications. The L&T trading-test gates (onboarding/, quiz/) were
# removed; their route files remain on disk for one cycle and will be
# deleted in a follow-up commit once we've confirmed nothing else (CI,
# scheduled jobs, telemetry) consumes /api/onboarding/status.
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
    from fastapi.responses import PlainTextResponse
    import pathlib

    path = pathlib.Path(__file__).parent.parent.parent / "static" / "apple-developer-merchantid-domain-association"
    if path.exists():
        return PlainTextResponse(path.read_text())
    return PlainTextResponse("", status_code=404)
