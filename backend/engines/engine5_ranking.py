import logging

from backend.core.models.classification import ClassifiedEvent
from backend.core.models.market import Market, Orderbook, MarketOrderbookStats
from backend.core.models.trading import RankedMarket, EventWithTopMarkets
from backend.adapters.kalshi.types import calculate_orderbook_stats

logger = logging.getLogger(__name__)


def rank_event_markets(
    event: ClassifiedEvent,
    orderbooks: dict[str, Orderbook],
) -> EventWithTopMarkets:
    """
    Rank markets inside an event by resting order activity.
    Sort: total_resting_order_quantity DESC → volume_24h DESC.
    Returns EventWithTopMarkets with top_markets list.
    """
    ranked: list[RankedMarket] = []

    for market in event.markets:
        ob = orderbooks.get(market.ticker, Orderbook(market_ticker=market.ticker))
        stats = calculate_orderbook_stats(market, ob)
        ranked.append(RankedMarket(
            market_ticker=market.ticker,
            volume=market.volume,
            spread_cents=stats.spread_cents or 0,
            yes_price=market.yes_bid or 0,
            no_price=market.no_bid or 0,
            rank=0,
            score=float(stats.total_resting_order_quantity),
        ))

    ranked.sort(
        key=lambda r: (-r.volume, r.spread_cents, -r.score),
    )
    for i, rm in enumerate(ranked):
        rm.rank = i + 1

    return EventWithTopMarkets(
        event_ticker=event.event_ticker,
        event_title=event.event_title or "",
        top_markets=ranked,
        total_volume=sum(r.volume for r in ranked),
        num_top_markets=len(ranked),
    )


def rank_all_events(
    event_books: list[tuple[ClassifiedEvent, dict[str, Orderbook]]]
) -> list[EventWithTopMarkets]:
    """Run ranking across all events."""
    return [rank_event_markets(e, ob) for e, ob in event_books]
