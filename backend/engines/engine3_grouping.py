from backend.core.models.classification import ClassificationResult, ClassifiedEvent
from backend.core.models.market import Market


def group_by_event_ticker(
    same_day_live_markets: list[tuple[Market, ClassificationResult]]
) -> list[ClassifiedEvent]:
    """
    Engine 3: Group same-day-live markets by event_ticker.

    An event qualifies if ANY child market passes SAME_DAY_LIVE_MARKET.
    Events are sorted by event_ticker for deterministic output.
    """
    by_event: dict[str, list[tuple[Market, ClassificationResult]]] = {}

    for market, classification in same_day_live_markets:
        ticker = market.event_ticker
        if ticker not in by_event:
            by_event[ticker] = []
        by_event[ticker].append((market, classification))

    events = []
    for ticker, markets in by_event.items():
        classifs = [c for _, c in markets]
        best_c = max(classifs, key=lambda c: c.confidence)
        total_volume = sum(m.volume for m, _ in markets)

        events.append(ClassifiedEvent(
            event_ticker=ticker,
            event_title=markets[0][0].title if markets else "",  # Initial value, enriched later
            markets=[m for m, _ in markets],
            classification=best_c,
            num_markets=len(markets),
            total_volume=total_volume,
        ))

    events.sort(key=lambda e: e.event_ticker)
    return events
