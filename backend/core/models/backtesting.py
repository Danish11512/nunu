"""Backtesting data models.

These dataclasses represent historical data consumed by the Phase 5
backtesting FeatureBuilder. They are not used at runtime — they exist
only for simulation/replay.

Terminology:
  - Prices are in integer cents (matching core conventions).
  - Sides use lowercase "yes" / "no" (matching TradeDecision.side).
  - Quantities are integer contract counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class HistoricalTrade:
    """A single historical trade from the exchange."""
    market_ticker: str
    trade_time: datetime
    yes_price: int          # cents (integer)
    no_price: int           # cents (integer)
    count: int              # contract count
    taker_side: Optional[str]  # "yes" | "no" | None
    is_block_trade: bool = False


@dataclass
class Candlestick:
    """Aggregated candlestick over a time bucket.
    Prices may be fractional (midpoints/averages) — stored as float
    but represent cents.
    """
    market_ticker: str
    bucket_start: datetime
    open_yes_price: float
    high_yes_price: float
    low_yes_price: float
    close_yes_price: float
    volume: int = 0          # integer contract count


@dataclass
class OrderbookSnapshot:
    """Point-in-time snapshot of the orderbook for a market."""
    market_ticker: str
    snapshot_time: datetime
    yes_bid_price: int      # cents
    yes_bid_quantity: int   # contracts
    no_bid_price: int       # cents
    no_bid_quantity: int    # contracts
    yes_total_depth: int    # contracts
    no_total_depth: int     # contracts
    spread: int             # cents


@dataclass
class HistoricalEvent:
    """A historical event used in backtesting.
    This is the top-level input to run_backtest().
    """
    event_ticker: str
    event_title: str
    start_time: datetime
    end_time: datetime
    child_market_tickers: list[str]
    settlement_result: Optional[str] = None  # "yes" | "no" | None
