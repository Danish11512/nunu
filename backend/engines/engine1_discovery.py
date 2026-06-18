import logging

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.market import Market
from backend.adapters.kalshi.types import parse_market

logger = logging.getLogger(__name__)


async def fetch_all_open_markets(client: MarketReader) -> list[Market]:
    """
    Engine 1: Fetch all currently open markets from Kalshi.

    Uses the MarketReader interface (not KalshiAdapter directly).
    The adapter handles pagination + dedup internally.

    Returns deduplicated list of all open Markets, or empty list on failure.
    """
    try:
        raw_markets = await client.fetch_markets(status="open", limit=1000)
        return [parse_market(m) for m in raw_markets] if raw_markets else []
    except Exception as e:
        logger.error(f"Engine 1 failed: {e}")
        return []
