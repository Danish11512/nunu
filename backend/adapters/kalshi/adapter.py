from __future__ import annotations

from typing import Any, Optional

from backend.core.interfaces.adapter import AbstractMarketAdapter
from backend.core.models.market import Market, MarketOrderbookStats, Orderbook

from .client import KalshiClient
from .types import calculate_orderbook_stats, parse_market, parse_orderbook


class KalshiAdapter(AbstractMarketAdapter):
    """Kalshi platform adapter implementing the abstract adapter contract.

    Properties (from :class:`AbstractMarketAdapter`):

    - ``name`` → ``"kalshi"``
    - ``timezone`` → ``"US/Eastern"``
    - ``supports_trading`` → ``True``
    - ``supports_websocket`` → ``True``

    :class:`MarketReader` methods delegate to :class:`KalshiClient` and return
    raw dicts (as required by the ABC contract). Convenience methods wrap them
    with domain model parsing.
    """

    def __init__(self, client: KalshiClient):
        self.client = client

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return "kalshi"

    @property
    def timezone(self) -> str:
        return "US/Eastern"

    @property
    def supports_trading(self) -> bool:
        return True

    @property
    def supports_websocket(self) -> bool:
        return True

    # ── MarketReader implementation (raw dicts per ABC contract) ──────────

    async def fetch_markets(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: return raw market dicts."""
        return await self.client.fetch_all_open_markets(**kwargs)

    async def fetch_orderbook(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: return raw orderbook dict."""
        return await self.client.get_orderbook(ticker, **kwargs)

    async def fetch_event(self, event_ticker: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: return raw event dict."""
        raw = await self.client.get_event(event_ticker, **kwargs)
        return raw or {}

    async def fetch_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: return raw event dicts."""
        data = await self.client.list_events(**kwargs)
        return data.get("events", [])

    # ── Trader implementation ─────────────────────────────────────────────

    async def place_order(
        self, ticker: str, side: str, price: int, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        """ABC: place a limit order. ``price`` = int cents, ``count`` = int contracts."""
        return await self.client.place_order(
            ticker=ticker, side=side, price=price, count=count, **kwargs
        )

    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """ABC: cancel an existing order."""
        return await self.client.cancel_order(order_id=order_id, **kwargs)

    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """ABC: get current positions."""
        return await self.client.get_positions(**kwargs)

    # ── Convenience methods (domain model wrappers) ───────────────────────

    async def get_all_open_markets(self) -> list[Market]:
        raw_markets = await self.fetch_markets()
        return [parse_market(m) for m in raw_markets]

    async def get_market(self, ticker: str) -> Optional[Market]:
        raw = await self.client.get_market(ticker)
        return parse_market(raw) if raw else None

    async def get_orderbook(self, ticker: str) -> Orderbook:
        raw = await self.fetch_orderbook(ticker)
        return parse_orderbook(raw, ticker)

    async def get_orderbook_stats(
        self, ticker: str,
    ) -> Optional[MarketOrderbookStats]:
        market = await self.get_market(ticker)
        if not market:
            return None
        orderbook = await self.get_orderbook(ticker)
        return calculate_orderbook_stats(market, orderbook)
