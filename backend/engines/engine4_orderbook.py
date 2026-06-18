import asyncio
import logging
from datetime import datetime, timezone

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.classification import ClassifiedEvent
from backend.core.models.market import Orderbook, OrderbookLevel
from backend.adapters.kalshi.types import parse_orderbook

logger = logging.getLogger(__name__)


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
                ob = parse_orderbook(raw, ticker)
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
