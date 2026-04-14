"""WebSocket endpoint for real-time signal push via Redis pub/sub."""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class SignalConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []
        self._listener_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.connections.append(websocket)
        logger.info("WS client connected (%d total)", len(self.connections))
        if self._listener_task is None or self._listener_task.done():
            self._listener_task = asyncio.create_task(self._redis_listener())

    def disconnect(self, websocket: WebSocket):
        if websocket in self.connections:
            self.connections.remove(websocket)
        logger.info("WS client disconnected (%d remaining)", len(self.connections))

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in self.connections:
                self.connections.remove(ws)

    async def _redis_listener(self):
        """Subscribe to Redis channel and broadcast new signals to all WS clients."""
        try:
            import redis.asyncio as aioredis
            from app.core.config import get_settings
            settings = get_settings()

            r = aioredis.from_url(settings.redis_url)
            pubsub = r.pubsub()
            await pubsub.subscribe("signal:new")
            logger.info("WebSocket Redis listener started on channel signal:new")

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    await self.broadcast(data)
                    logger.debug("Broadcast signal id=%s to %d WS clients", data.get("id"), len(self.connections))
                except Exception:
                    logger.warning("Failed to parse/broadcast Redis message", exc_info=True)
        except Exception:
            logger.warning("Redis pub/sub listener failed — WS will fall back to polling", exc_info=True)


manager = SignalConnectionManager()


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
