from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import websockets

from backend.utils.auth_utils import KalshiSigner  # RSA-PSS signer for WS

logger = logging.getLogger(__name__)


class KalshiWebSocket:
    """WebSocket client for Kalshi real-time updates (RSA-PSS auth).

    Uses :class:`backend.utils.auth_utils.KalshiSigner` (RSA-PSS) for
    connect authentication headers — same signing as REST API.
    Each callback is wrapped in try/except so one bad handler doesn't
    break the listen loop. On reconnect, subscribed tickers are re-sent.
    Reconnect uses exponential backoff (1s→60s cap) with jitter.
    """

    def __init__(
        self,
        url: str = "wss://api.elections.kalshi.com/trade-api/ws/v2",
        api_key_id: str = "",
        private_key: str = "",
    ):
        self.url = url
        self._api_key_id = api_key_id
        self._signer = KalshiSigner(private_key_pem=private_key) if private_key else None
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._callbacks: list[Callable[[dict[str, Any]], Awaitable[None]]] = []
        self._subscribed_tickers: list[str] = []
        self._reconnect_delay = 1.0

    def on_message(self, callback: Callable[[dict[str, Any]], Awaitable[None]]) -> None:
        """Register a callback invoked on each decoded message."""
        self._callbacks.append(callback)

    async def connect(self) -> None:
        """Connect with RSA-PSS API key auth via headers."""
        import time
        ts = str(int(time.time() * 1000))  # epoch ms — WS expects ms, not ISO
        message = ts + "GET" + "/trade-api/ws/v2"
        sig = self._signer.sign(message) if self._signer else ""
        headers = {
            "KALSHI-ACCESS-KEY": self._api_key_id,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
        self._ws = await websockets.connect(self.url, extra_headers=headers)
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
        """Listen loop with callback isolation, reconnect, and re-subscribe.

        Reconnect uses exponential backoff (1s→60s cap) with jitter.
        Resets delay on successful reconnection.
        """
        import random

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

                # Reset delay on successful recv
                self._reconnect_delay = 1.0

            except websockets.exceptions.ConnectionClosed:
                delay = min(self._reconnect_delay, 60.0)
                jitter = random.uniform(0.5, 1.5)
                sleep_time = delay * jitter
                logger.warning(
                    "WebSocket disconnected. Reconnecting in %.1fs...", sleep_time
                )
                await asyncio.sleep(sleep_time)
                if not self._running:
                    break
                await self._reconnect()
                self._reconnect_delay = min(delay * 2, 60.0)

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
