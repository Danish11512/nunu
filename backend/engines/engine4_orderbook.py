import asyncio
import logging
from datetime import datetime

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.classification import ClassifiedEvent
from backend.core.models.market import Orderbook, OrderbookLevel

logger = logging.getLogger(__name__)


def parse_orderbook_response(raw: dict, ticker: str) -> Orderbook:
    """Parse Kalshi API orderbook response into Orderbook model.

    The API returns {"yes": [{"price": 65, "count": 1000}, ...],
    "no": [{"price": 35, "count": 800}, ...]} with int cents and int contracts.
    """
    yes_raw = raw.get("yes", [])
    no_raw = raw.get("no", [])

    def parse_levels(levels: list) -> list[OrderbookLevel]:
        if not levels:
            return []
        return [
            OrderbookLevel(price=level["price"], count=level["count"])
            for level in levels
        ]

    return Orderbook(
        market_ticker=ticker,
        yes_side=parse_levels(yes_raw),
        no_side=parse_levels(no_raw),
        fetch_time=datetime.now(),
    )


async def fetch_orderbooks(
    events: list[ClassifiedEvent],
    client: MarketReader,
    concurrency: int = 10,
) -> list[tuple[ClassifiedEvent, dict[str, Orderbook]]]:
    """
    Engine 4: Fetch orderbooks for all markets across all qualified events.
    Markets with no orderbook data still get an empty Orderbook.
    Uses bounded concurrency via asyncio.Semaphore.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def fetch_one(ticker: str) -> tuple[str, Orderbook]:
        async with semaphore:
            try:
                raw = await client.fetch_orderbook(ticker)
                ob = parse_orderbook_response(raw, ticker)
                return ticker, ob
            except Exception as e:
                logger.warning(f"Orderbook fetch failed for {ticker}: {e}")
                return ticker, Orderbook(market_ticker=ticker)

    result: list[tuple[ClassifiedEvent, dict[str, Orderbook]]] = []

    for event in events:
        tickers = [m.ticker for m in event.markets]
        tasks = [fetch_one(t) for t in tickers]
        results = await asyncio.gather(*tasks)
        orderbooks = dict(results)
        result.append((event, orderbooks))

    return result
