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
        """Subscribe to Redis channel and broadcast new signals to all WS clients.

        Cleanup contract: every code path that opens a Redis connection
        unsubscribes and closes it. Audit follow-up 2026-05-05 — the
        previous version had no `finally` block, so any exception out of
        `pubsub.listen()` (Redis hiccup, asyncio CancelledError on app
        reload, malformed message that escaped the inner try) abandoned
        the connection. Since `connect()` re-spawns the listener on the
        next WS handshake when `_listener_task.done()` is True, every
        outage of the listener leaked one Redis connection until the
        process exhausted the connection limit or was restarted.
        """
        r = None
        pubsub = None
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
        finally:
            # Best-effort close — both `pubsub.aclose()` and `r.aclose()`
            # can themselves raise if the underlying socket is already
            # half-closed (Redis went away, container restart, …). Swallow
            # those because the goal is "release the FD," and we already
            # know we're tearing down on an error path.
            if pubsub is not None:
                try:
                    await pubsub.unsubscribe()
                except Exception:
                    pass
                try:
                    await pubsub.aclose()
                except Exception:
                    pass
            if r is not None:
                try:
                    await r.aclose()
                except Exception:
                    pass


manager = SignalConnectionManager()


@router.websocket("/ws/signals")
async def websocket_signals(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
