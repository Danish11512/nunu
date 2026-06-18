# Adapter Contract Specification

## Purpose

Define the contract that every prediction market platform adapter must implement to integrate with the generic scanner pipeline.

---

## Core Interfaces (Python ABCs)

```python
from abc import ABC, abstractmethod
from typing import Any


class MarketReader(ABC):
    """Read-only market data access."""

    @abstractmethod
    async def fetch_markets(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Fetch all available markets (paginated internally)."""
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
    async def place_order(
        self, ticker: str, side: str, price: int, count: int, **kwargs: Any
    ) -> dict[str, Any]:
        """Place a limit order. Price in cents."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, **kwargs: Any) -> dict[str, Any]:
        """Cancel an existing order by ID."""
        ...

    @abstractmethod
    async def get_positions(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Get current positions."""
        ...


class AbstractMarketAdapter(MarketReader, Trader, ABC):
    """Combined interface for full market access (read + write)."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable adapter name (e.g. 'Kalshi')."""
        ...

    @property
    @abstractmethod
    def timezone(self) -> str:
        """Exchange timezone (e.g. 'US/Eastern')."""
        ...

    @property
    @abstractmethod
    def supports_trading(self) -> bool:
        """Whether this adapter supports placing orders."""
        ...

    @property
    @abstractmethod
    def supports_websocket(self) -> bool:
        """Whether this adapter supports WebSocket streaming."""
        ...
```

## Supporting Types & Key Domain Objects

All adapter method signatures use `dict[str, Any]` / `list[dict[str, Any]]` for return types. The pipeline constructs domain objects from raw dicts using `backend.core.models`.

Key domain objects (Python dataclasses in `backend.core.models`):

| Object | Defined In | Key Fields |
|--------|-----------|------------|
| `Market` | `backend.core.models.market` | `ticker`, `event_ticker`, `yes_bid`, `yes_ask`, `no_bid`, `no_ask` (all `int` cents) |
| `Orderbook` | `backend.core.models.market` | `market_ticker`, `yes_side: list[OrderbookLevel]`, `no_side: list[OrderbookLevel]` |
| `OrderbookLevel` | `backend.core.models.market` | `price: int` (cents), `count: int` |
| `MarketOrderbookStats` | `backend.core.models.market` | `market_ticker`, `event_ticker`, `spread_cents`, `total_resting_order_quantity` |
| `ClassificationResult` | `backend.core.models.classification` | `market_ticker`, `event_ticker`, `is_same_day_live`, `confidence` |
| `ClassifiedEvent` | `backend.core.models.classification` | `event_ticker`, `markets: list[Market]`, `classification` |
| `OrderCandidate` | `backend.core.models.trading` | `event_ticker`, `market_ticker`, `side`, `price: int` (cents) |
| `ProgressBasedOrderCandidate` | `backend.core.models.trading` | Extends `OrderCandidate`; `threshold_pct`, `is_overtime` |
| `ValidatedOrderCandidate` | `backend.core.models.trading` | `original_candidate`, `is_valid`, `max_contracts`, `risk_score` |
| `EventWithTopMarkets` | `backend.core.models.trading` | `event_ticker`, `top_markets: list[RankedMarket]` |
| `KalshiConfig` | `backend.config.settings` | Pydantic model; `api_base_url`, rate limits, auth |

**Live Connection (forward-looking):** WebSocket streaming capability is indicated via the `supports_websocket` property. A `LiveConnection` abstraction will be designed when live mode is implemented.

## Contract Rules

1. **Adapters must not filter** — return all open markets, all orderbook levels. Filtering is the pipeline's job.
2. **Adapters must throw typed errors** — `RateLimitError`, `AuthError`, `NetworkError`, `InvalidResponseError`.
3. **Adapters must handle pagination** internally — the pipeline gets a complete result.
4. **Adapters must normalize timestamps** to ISO 8601 UTC strings.
5. **Adapters must normalize prices** to int cents (not dollars, not token units).
6. **Adapters should batch** when the provider supports it, but must also work with individual requests.
