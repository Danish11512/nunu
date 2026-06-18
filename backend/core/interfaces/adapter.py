from abc import ABC, abstractmethod
from typing import Any

import httpx


class MarketReader(ABC):
    """Read-only market data access."""

    @abstractmethod
    async def fetch_markets(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch all available markets."""
        ...

    @abstractmethod
    async def fetch_orderbook(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch orderbook for a single market by ticker."""
        ...

    @abstractmethod
    async def fetch_event(self, event_ticker: str, **kwargs: Any) -> dict[str, Any]:
        """Fetch a single event by ticker."""
        ...

    @abstractmethod
    async def fetch_events(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch all events."""
        ...


class Trader(ABC):
    """Write-only trading operations."""

    @abstractmethod
    async def place_order(self, ticker: str, side: str, price: int, count: int, **kwargs: Any) -> dict[str, Any]:
        """Place a limit order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """Cancel an existing order."""
        ...

    @abstractmethod
    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get current positions."""
        ...


class AbstractMarketAdapter(MarketReader, Trader, ABC):
    """Combined interface for full market access (read + write).
    
    Properties that adapters should provide:
    - name: str — adapter identifier
    - timezone: str — exchange timezone
    - supports_trading: bool — whether trading operations are available
    - supports_websocket: bool — whether websocket streaming is available
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name."""
        ...

    @property
    @abstractmethod
    def timezone(self) -> str:
        """Exchange timezone string (e.g. 'US/Eastern')."""
        ...

    @property
    @abstractmethod
    def supports_trading(self) -> bool:
        """Whether this adapter supports placing orders."""
        ...

    @property
    @abstractmethod
    def supports_websocket(self) -> bool:
        """Whether this adapter supports websocket streaming."""
        ...
