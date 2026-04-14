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
from app.api.routes.agents import router as agents_router  # noqa: E402
from app.api.routes.api_keys import router as api_keys_router  # noqa: E402
from app.api.routes.subscriptions import router as subs_router  # noqa: E402
from app.api.routes.auth import router as auth_router  # noqa: E402

app.include_router(trading_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(api_keys_router, prefix="/api")
app.include_router(subs_router, prefix="/api")
app.include_router(auth_router, prefix="/api")

from app.api.routes.b2b import router as b2b_router  # noqa: E402

app.include_router(b2b_router, prefix="/api")
