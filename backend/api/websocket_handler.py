"""WebSocket handler for real-time event streaming."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.api.errors import WSMessage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        if channel not in self._connections:
            self._connections[channel] = set()
        self._connections[channel].add(ws)
        logger.info(f"WS connected: channel={channel} total={len(self._connections[channel])}")

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        self._connections.get(channel, set()).discard(ws)
        logger.info(f"WS disconnected: channel={channel}")

    async def broadcast(self, channel: str, type_: str, data: Any) -> None:
        message = WSMessage(
            type=type_,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ).model_dump_json()
        stale = set()
        for ws in self._connections.get(channel, set()):
            try:
                await ws.send_text(message)
            except Exception:
                stale.add(ws)
        for ws in stale:
            self.disconnect(channel, ws)

    @property
    def connection_counts(self) -> dict[str, int]:
        return {ch: len(wss) for ch, wss in self._connections.items()}


manager = ConnectionManager()


@router.websocket("/ws/scanner")
async def ws_scanner(ws: WebSocket):
    await manager.connect("scanner", ws)
    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect("scanner", ws)
    except Exception as e:
        logger.error(f"WS scanner error: {e}")
        manager.disconnect("scanner", ws)


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await manager.connect("events", ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("events", ws)
    except Exception as e:
        logger.error(f"WS events error: {e}")
        manager.disconnect("events", ws)


@router.websocket("/ws/candidates")
async def ws_candidates(ws: WebSocket):
    await manager.connect("candidates", ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("candidates", ws)
    except Exception as e:
        logger.error(f"WS candidates error: {e}")
        manager.disconnect("candidates", ws)


@router.websocket("/ws/trades")
async def ws_trades(ws: WebSocket):
    await manager.connect("trades", ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect("trades", ws)
    except Exception as e:
        logger.error(f"WS trades error: {e}")
        manager.disconnect("trades", ws)
