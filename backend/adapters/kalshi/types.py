from __future__ import annotations

from typing import Any

from backend.core.models.market import (
    Market,
    MarketOrderbookStats,
    Orderbook,
    OrderbookLevel,
)
from backend.utils.datetime_utils import parse_date


def _to_int_cents(val: Any) -> int | None:
    """Normalize a price value to integer cents.

    Handles floats (dollars like ``0.65`` → ``65``), strings, and ``None``.
    If a float is already > 100 it is treated as raw cents.
    """
    if val is None:
        return None
    if isinstance(val, str):
        val = float(val)
    if isinstance(val, float):
        # If it looks like dollars (e.g. 0.65), multiply by 100
        if val < 100:
            return int(round(val * 100))
        return int(val)
    if isinstance(val, int):
        return val
    return None


def parse_market(raw: dict[str, Any]) -> Market:
    """Map a Kalshi API market dict → :class:`Market` dataclass.

    Handles all nullable fields with ``.get()`` and ``None`` defaults.
    Prices are normalized to integer cents via :func:`_to_int_cents`.
    Timestamps are parsed via :func:`backend.utils.datetime_utils.parse_date`.
    """
    return Market(
        ticker=raw.get("ticker", ""),
        event_ticker=raw.get("event_ticker", ""),
        title=raw.get("title", ""),
        status=raw.get("status", ""),
        yes_ask=_to_int_cents(raw.get("yes_ask")),
        yes_bid=_to_int_cents(raw.get("yes_bid")),
        no_ask=_to_int_cents(raw.get("no_ask")),
        no_bid=_to_int_cents(raw.get("no_bid")),
        volume=int(raw.get("volume", 0)),
        open_interest=int(raw.get("open_interest", 0)),
        expiry=parse_date(raw.get("expected_expiration_time")),
        expiry_iso=raw.get("expected_expiration_time"),
        create_date=raw.get("create_date"),
        settlement_date=raw.get("settlement_date"),
        close_date=raw.get("close_date"),
        result=raw.get("result"),
        rules_primary=raw.get("rules_primary"),
        rule_key=raw.get("rule_key"),
        volume_24h=_to_int_cents(raw.get("volume_24h")),
        volume_24h_adjusted=_to_int_cents(raw.get("volume_24h_adjusted")),
    )


def parse_orderbook(raw: dict[str, Any], ticker: str) -> Orderbook:
    """Map a Kalshi API orderbook dict → :class:`Orderbook` dataclass.

    The Kalshi API returns::

        {"yes": [{"price": 65, "count": 1000}, ...],
         "no":  [{"price": 35, "count": 2000}, ...]}

    Levels are sorted ascending by price. Empty orderbooks produce empty
    side lists.
    """
    def _parse_levels(levels: list[dict[str, Any]] | None) -> list[OrderbookLevel]:
        if not levels:
            return []
        result: list[OrderbookLevel] = []
        for level in levels:
            try:
                result.append(
                    OrderbookLevel(
                        price=int(level.get("price", 0)),
                        count=int(level.get("count", 0)),
                    )
                )
            except (ValueError, TypeError):
                continue
        result.sort(key=lambda l: l.price)
        return result

    return Orderbook(
        market_ticker=ticker,
        yes_side=_parse_levels(raw.get("yes")),
        no_side=_parse_levels(raw.get("no")),
        fetch_time=parse_date(raw.get("fetch_time")),
    )


def calculate_orderbook_stats(
    market: Market,
    orderbook: Orderbook,
) -> MarketOrderbookStats:
    """Derive statistics from a market + its orderbook.

    Computes:
        - ``spread_cents``: best yes_ask – best yes_bid (``None`` if either missing)
        - ``total_resting_order_quantity``: sum of all counts across both sides
        - Best bid/ask prices from orderbook levels (fallback to market fields)
    """
    # Best bid/ask from orderbook levels (first = best price for bids,
    # last = best price for asks in sorted list)
    yes_bid: int | None = orderbook.yes_side[0].price if orderbook.yes_side else market.yes_bid
    yes_ask: int | None = orderbook.yes_side[-1].price if orderbook.yes_side else market.yes_ask
    no_bid: int | None = orderbook.no_side[0].price if orderbook.no_side else market.no_bid
    no_ask: int | None = orderbook.no_side[-1].price if orderbook.no_side else market.no_ask

    # Spread: difference between best yes_ask and best yes_bid
    spread: int | None = None
    if yes_bid is not None and yes_ask is not None:
        spread = abs(yes_ask - yes_bid)

    # Total resting quantity across both sides
    total_resting = sum(level.count for level in orderbook.yes_side) + sum(
        level.count for level in orderbook.no_side
    )

    return MarketOrderbookStats(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        spread_cents=spread,
        yes_bid=yes_bid,
        yes_ask=yes_ask,
        no_bid=no_bid,
        no_ask=no_ask,
        last_price=(yes_bid or 0),
        volume=market.volume,
        open_interest=market.open_interest,
        volume_24h=market.volume_24h,
        total_resting_order_quantity=total_resting,
    )
