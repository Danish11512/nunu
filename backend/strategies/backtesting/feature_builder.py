"""Feature builder for backtesting.

Enriches MarketFeatures from historical trade, candle, and orderbook data.
This is the bridge between raw historical data and the strategy interface.
"""

from datetime import datetime
from typing import Callable, Optional

from backend.core.interfaces.strategy import MarketFeatures
from backend.core.models.backtesting import (
    HistoricalTrade,
    OrderbookSnapshot,
)


def build_market_features(
    ticker: str,
    trades: list[HistoricalTrade],
    orderbook_snapshot: Optional[OrderbookSnapshot],
    entry_time: datetime,
    yes_price_at_entry: int,
    no_price_at_entry: int,
    reference_yes_price: Optional[int] = None,
) -> MarketFeatures:
    """Build a MarketFeatures instance from historical data.
    
    Args:
        ticker: Market ticker.
        trades: Historical trades for this market before entry_time.
        orderbook_snapshot: Orderbook snapshot at or before entry_time.
        entry_time: The simulated entry time (trades before this are used).
        yes_price_at_entry: YES price at entry in cents.
        no_price_at_entry: NO price at entry in cents.
        reference_yes_price: Optional reference YES price for momentum calc.
    
    Returns:
        A populated MarketFeatures instance with extended backtesting fields.
    """
    # Filter trades before entry time
    trades_before = [t for t in trades if t.trade_time < entry_time]
    
    # Aggregate trade data
    total_vol = sum(t.count for t in trades_before)
    yes_vol = sum(t.count for t in trades_before if t.taker_side == "yes")
    no_vol = sum(t.count for t in trades_before if t.taker_side == "no")
    trade_count = len(trades_before)
    
    # Price momentum
    if reference_yes_price is not None:
        yes_price_momentum = float(yes_price_at_entry - reference_yes_price)
    else:
        yes_price_momentum = 0.0
    
    # Orderbook-derived fields
    if orderbook_snapshot is not None:
        yes_total_depth = orderbook_snapshot.yes_total_depth
        no_total_depth = orderbook_snapshot.no_total_depth
        spread_cents = orderbook_snapshot.spread
        yes_bid = orderbook_snapshot.yes_bid_price
        no_bid = orderbook_snapshot.no_bid_price
    else:
        yes_total_depth = 0
        no_total_depth = 0
        spread_cents = abs(yes_price_at_entry - no_price_at_entry)
        yes_bid = yes_price_at_entry
        no_bid = no_price_at_entry
    
    return MarketFeatures(
        ticker=ticker,
        volume=total_vol,
        yes_bid=yes_bid,
        no_bid=no_bid,
        spread_cents=spread_cents,
        total_executed_volume=total_vol,
        yes_executed_volume=yes_vol,
        no_executed_volume=no_vol,
        trade_count=trade_count,
        yes_price_momentum=yes_price_momentum,
        yes_total_depth=yes_total_depth,
        no_total_depth=no_total_depth,
    )
