from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Market:
    """A single Kalshi prediction market contract."""

    ticker: str  # e.g. "KXLYDYX"
    event_ticker: str  # e.g. "PRESIDENTS-DAY-24H"
    title: str
    status: str  # "open" | "active" | "closed" | "settled"
    yes_ask: int | None  # Price in cents
    yes_bid: int | None
    no_ask: int | None
    no_bid: int | None
    volume: int  # Total contracts traded
    open_interest: int
    expiry: datetime | None  # expected_expiration_time from API
    expiry_iso: str | None  # Raw ISO string for serialization
    create_date: str | None  # ISO date
    settlement_date: str | None
    close_date: str | None
    result: str | None  # "yes" | "no" | None (before settlement)
    rules_primary: str | None  # The main "Yes/No" rule
    rule_key: str | None
    yes_sub_title: str = ""  # Shortened title from Kalshi V2 (e.g. "BTC >$100k 12am EDT")
    volume_24h: int | None = None  # 24-hour volume
    volume_24h_adjusted: int | None = None


@dataclass
class OrderbookLevel:
    """A single price level in the orderbook."""

    price: int  # In cents
    count: int  # Number of contracts at this level


@dataclass
class Orderbook:
    """Orderbook snapshot for a single market."""

    market_ticker: str
    yes_side: list[OrderbookLevel] = field(default_factory=list)
    no_side: list[OrderbookLevel] = field(default_factory=list)
    fetch_time: datetime | None = None


@dataclass
class MarketOrderbookStats:
    """Derived orderbook statistics for a market."""

    market_ticker: str  # NOT market_id — consistent with Market.ticker
    event_ticker: str
    spread_cents: int | None = None
    yes_bid: int | None = None
    yes_ask: int | None = None
    no_bid: int | None = None
    no_ask: int | None = None
    last_price: int | None = None
    volume: int = 0
    open_interest: int = 0
    volume_24h: int | None = None
    total_resting_order_quantity: int = 0
    yes_order_quantity: int = 0
    no_order_quantity: int = 0
    depth_level_count: int = 0
