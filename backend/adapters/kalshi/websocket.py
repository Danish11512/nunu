from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import websockets

from .auth import KalshiSigner  # PKCS1v15 signer — correct for WS auth

logger = logging.getLogger(__name__)


class KalshiWebSocket:
    """WebSocket client for Kalshi real-time updates (PKCS1v15 auth).

    Uses :class:`.auth.KalshiSigner` for connect authentication headers.
    Each callback is wrapped in try/except so one bad handler doesn't
    break the listen loop. On reconnect, subscribed tickers are re-sent.
    """

    def __init__(
        self,
        url: str = "wss://api.elections.kalshi.com/trade-api/ws/v2",
        api_key_id: str = "",
        private_key: str = "",
    ):
        self.url = url
        self._signer = KalshiSigner(api_key_id=api_key_id, private_key_pem=private_key)
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._callbacks: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._subscribed_tickers: list[str] = []

    def on_message(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback invoked on each decoded message."""
        self._callbacks.append(callback)

    async def connect(self) -> None:
        """Connect with PKCS1v15 API key auth via headers."""
        headers = self._signer.get_headers("GET", "/trade-api/ws/v2")
        self._ws = await websockets.connect(self.url, additional_headers=headers)
        logger.info("WebSocket connected to %s", self.url)

    async def subscribe(self, tickers: list[str]) -> None:
        """Subscribe to ``orderbook_delta`` channel for given tickers.

        Stores tickers so they can be re-subscribed on reconnect.
        """
        self._subscribed_tickers = list(tickers)
        message = {
            "id": 1,
            "cmd": "subscribe",
            "params": {
                "channels": ["orderbook_delta"],
                "market_tickers": tickers,
            },
        }
        await self._ws.send(json.dumps(message))
        logger.info("Subscribed to %d tickers.", len(tickers))

    async def listen(self) -> None:
        """Listen loop with callback isolation, reconnect, and re-subscribe."""
        self._running = True
        while self._running:
            try:
                raw = await self._ws.recv()
                data = json.loads(raw)

                # Dispatch each callback in isolation
                for cb in self._callbacks:
                    try:
                        await cb(data)
                    except Exception as exc:
                        logger.error(
                            "WebSocket callback error: %s", exc, exc_info=True
                        )

            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket disconnected. Reconnecting in 5s...")
                await asyncio.sleep(5)
                if not self._running:
                    break
                await self._reconnect()

            except Exception as exc:
                logger.error("WebSocket listen error: %s", exc, exc_info=True)
                await asyncio.sleep(1)

    async def _reconnect(self) -> None:
        """Reconnect and re-subscribe previously subscribed tickers."""
        try:
            await self.connect()
            if self._subscribed_tickers:
                await self.subscribe(self._subscribed_tickers)
                logger.info(
                    "Re-subscribed to %d tickers after reconnect.",
                    len(self._subscribed_tickers),
                )
        except Exception as exc:
            logger.error("WebSocket reconnect failed: %s", exc, exc_info=True)

    async def close(self) -> None:
        """Disconnect and stop the listen loop."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
