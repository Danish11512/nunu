from backend.core.models.classification import ClassifiedEvent
from backend.core.models.market import Orderbook
from backend.core.models.trading import EventWithTopMarkets
from backend.engines.engine5_ranking import rank_event_markets


def rerank_event(event: ClassifiedEvent, orderbooks: dict[str, Orderbook]) -> EventWithTopMarkets:
    """Re-rank a single event when its orderbooks change."""
    return rank_event_markets(event, orderbooks)
