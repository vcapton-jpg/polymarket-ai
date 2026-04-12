"""FastAPI application and routes."""

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.database import get_db_session, engine
from app.db.models import Base

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup: Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown: Close connections
    await engine.dispose()


# Create FastAPI app
app = FastAPI(
    title="Signal API",
    description="Prediction market intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health endpoint
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": settings.app_version}


# Signals endpoints
@app.get("/api/signals")
async def list_signals(
    bucket: Optional[str] = Query(None),
    min_score: int = Query(0, ge=0, le=100),
    direction: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """List signals with filters."""
    from sqlalchemy import select, desc, asc

    query = select(Signal).order_by(desc(Signal.signal_date))

    if bucket:
        query = query.join(Event).where(Event.bucket == bucket)

    if min_score > 0:
        query = query.where(Signal.score >= min_score)

    if direction:
        query = query.where(Signal.direction == direction)

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    signals = result.scalars().all()

    return {"signals": [s.__dict__ for s in signals], "total": len(signals)}


@app.get("/api/signals/{signal_id}")
async def get_signal_detail(
    signal_id: int,
    db: AsyncSession = Depends(get_db_session),
):
    """Get signal detail."""
    from sqlalchemy import select

    query = select(Signal).where(Signal.id == signal_id)
    result = await db.execute(query)
    signal = result.scalar_one_or_none()

    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return signal.__dict__


# Markets endpoints
@app.get("/api/markets")
async def list_markets(
    limit: int = Query(50, ge=1, le=100),
    category: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """List active markets."""
    from sqlalchemy import select

    query = select(Market).limit(limit)
    if category:
        query = query.where(Market.category == category)

    result = await db.execute(query)
    markets = result.scalars().all()

    return {"markets": [m.__dict__ for m in markets]}


# Events endpoints
@app.get("/api/events")
async def list_events(
    limit: int = Query(20, ge=1, le=100),
    bucket: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """List recent events."""
    from sqlalchemy import select, desc

    query = select(Event).order_by(desc(Event.created_at)).limit(limit)

    if bucket:
        query = query.where(Event.bucket == bucket)

    result = await db.execute(query)
    events = result.scalars().all()

    return {"events": [e.__dict__ for e in events]}


# Analytics endpoints
@app.get("/api/analytics/accuracy")
async def get_signal_accuracy(
    db: AsyncSession = Depends(get_db_session),
):
    """Get signal accuracy statistics."""
    # Query for accuracy metrics
    return {"accuracy": 0.0, "total_signals": 0, "resolved": 0}


@app.get("/api/analytics/costs")
async def get_llm_costs(
    db: AsyncSession = Depends(get_db_session),
):
    """Get LLM cost dashboard."""
    # Query for cost aggregation
    return {"daily_cost": 0.0, "total_tokens": 0}


# WebSocket for real-time signals
class SignalConnectionManager:
    """Manager for WebSocket connections."""

    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """Connect a websocket."""
        await websocket.accept()
        self.connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """Disconnect a websocket."""
        if websocket in self.connections:
            self.connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connections."""
        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = SignalConnectionManager()


@app.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    """WebSocket for real-time signals."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now
            await websocket.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Import models for endpoint queries
from app.db.models import Signal, Event, Market