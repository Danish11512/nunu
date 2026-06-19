import logging

from backend.core.interfaces.adapter import MarketReader
from backend.core.models.market import Market
from backend.adapters.kalshi.types import parse_market

logger = logging.getLogger(__name__)


async def fetch_all_open_markets(client: MarketReader) -> list[Market]:
    """
    Engine 1: Fetch open markets from Kalshi that have active trading volume.

    Fetches the first 1000 open markets (newest first, excludes multivariate combos)
    and filters to only those with non-zero trading volume — zero-volume markets
    have no trades and aren't useful for monitoring.

    Uses the MarketReader interface (not KalshiAdapter directly).
    The adapter handles pagination + dedup internally.

    Returns list of active Markets, or empty list on failure.
    """
    try:
        raw_markets = await client.fetch_markets(status="open", limit=1000)
        parsed = [parse_market(m) for m in raw_markets] if raw_markets else []
        active = [m for m in parsed if m.volume > 0]
        logger.info(
            "Engine 1 (discovery): %d/%d markets have trading volume.",
            len(active),
            len(parsed),
        )
        return active
    except Exception as e:
        logger.error(
            "Engine 1 (discovery) failed: %s. "
            "Check that Kalshi API credentials are configured and the API is reachable.",
            e,
        )
        return []
