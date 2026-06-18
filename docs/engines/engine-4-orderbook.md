# Engine 4: Market Orderbook Fetch Engine

## Purpose

For each same-day live market across all qualified events, fetch the current orderbook. This enriches events with real-time bidding data — it does **not** decide whether an event qualifies.

## Input

```python
@dataclass
class Engine4Input:
    events: list[ClassifiedEvent]        # From Engine 3
```

## Output

```python
from backend.core.models.market import Market, Orderbook, OrderbookLevel
# Engine 4 uses Market and Orderbook directly from the domain models
# The adapter's types.parse_orderbook handles API format conversion

@dataclass
class MarketWithOrderbook:
    market: Market
    orderbook: Orderbook

@dataclass
class EventWithOrderbooks:
    event_ticker: str
    event_title: str
    markets: list[MarketWithOrderbook]
    total_volume: int = 0

@dataclass
class Engine4Output:
    events: list[EventWithOrderbooks]
```

## Kalshi Endpoint

```
GET https://api.elections.kalshi.com/trade-api/v2/markets/{ticker}/orderbook
```

### Response Format

The Kalshi orderbook API returns **bids only** for each outcome token:

```json
{
  "yes": [{"price": 65, "count": 1000}, {"price": 64, "count": 500}],
  "no":  [{"price": 35, "count": 800}, {"price": 34, "count": 300}]
}
```

### Orderbook Semantics (Kalshi)

- `yes` = levels for the YES outcome — each level has `price` (int cents) and `count` (int contracts)
- `no` = levels for the NO outcome
- The orderbook endpoint returns **bids only** — there are no direct asks
- `parse_orderbook()` in `types.py` handles the conversion to `Orderbook` domain objects
- `calculate_orderbook_stats()` derives best bid from the lowest price level in each side

## Implementation

```python
async def fetch_orderbooks(events: list[ClassifiedEvent], client: MarketReader) -> Engine4Output:
    """
    Fetch orderbooks for all markets across all qualified events.
    Markets with no orderbook data are still included (empty orderbook).

    Uses MarketReader.fetch_orderbook(ticker) -> dict[str, Any].
    """
    result_events = []

    for event in events:
        markets_with_books = []

        for market in event.markets:
            try:
                raw = await client.fetch_orderbook(market.ticker)
                orderbook = parse_orderbook_response(raw, market.ticker)
            except Exception:
                # Network error — log and continue with empty book
                logger.warning(f"Failed to fetch orderbook for {market.ticker}")
                orderbook = Orderbook(market_ticker=market.ticker)

            markets_with_books.append(MarketWithOrderbook(
                market=market,
                orderbook=orderbook,
            ))

        total_vol = sum(m.volume for m in event.markets if isinstance(m.volume, int))
        result_events.append(EventWithOrderbooks(
            event_ticker=event.event_ticker,
            event_title=event.event_title,
            markets=markets_with_books,
            total_volume=total_vol,
        ))

    return Engine4Output(events=result_events)


def parse_orderbook_response(raw: dict[str, Any], ticker: str) -> Orderbook:
    """Convert raw Kalshi API orderbook response to Orderbook model.

    The API returns ``{"yes": [{"price": 65, "count": 1000}, ...],
    "no": [{"price": 35, "count": 800}, ...]}`` where each level
    has ``price`` in int cents and ``count`` in int contracts.
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
```

## Orderbook Parsing

```python
def parse_orderbook_levels(
    yes: list[dict[str, int | float]] | None,
    no: list[dict[str, int | float]] | None,
) -> tuple[list[OrderbookLevel], list[OrderbookLevel]]:
    """Parse Kalshi orderbook level dicts into OrderbookLevel objects (int cents).

    Each level has ``price`` (int cents) and ``count`` (int contracts).
    """

    def parse_levels(levels: list[dict[str, int | float]] | None) -> list[OrderbookLevel]:
        if not levels:
            return []
        return [
            OrderbookLevel(price=int(level["price"]), count=int(level["count"]))
            for level in levels
        ]

    return (
        parse_levels(yes),
        parse_levels(no),
    )
```

## Concurrency

Fetch orderbooks **concurrently** — don't serialize. Kalshi has rate limits, so use a bounded semaphore:

```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

async def fetch_with_limit(ticker: str) -> Orderbook:
    async with semaphore:
        raw = await client.fetch_orderbook(ticker)
        return parse_orderbook_response(raw, ticker)
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Orderbook not found (404) | Include market with empty orderbook — it may get orders later |
| Rate limit (429) | Backoff and retry, then skip if exhausted |
| Network timeout | Log warning, skip market, continue pipeline |
| All orderbooks fail | Return events with empty orderbooks — pipeline continues |

## Why Not Filter Here?

This engine fetches orderbooks for **all** same-day live markets, even ones with zero resting orders. That's by design:

- A market with 0 orders at snapshot time may get orders 5 seconds later
- The live update system (WebSocket) will patch orderbooks incrementally
- Filtering here would cause flickering — markets disappearing and reappearing

## Performance Notes

- Expected: 50–500 same-day live markets per scan
- Each orderbook fetch: ~100-300ms
- Concurrent fetch with semaphore(10): ~1-15s total
- Optimization path: batch orderbook endpoint if Kalshi supports it

## Dependencies

- `backend/core/interfaces/adapter.py` — `MarketReader` (provides `fetch_orderbook(ticker)`)
- `backend.core.models.market` — `Orderbook`, `OrderbookLevel`, `Market`

## Testing

```python
async def test_parses_kalshi_fp_format():
    """[["0.65", "1000"], ...] → OrderbookLevel objects."""
    ...

async def test_handles_empty_orderbook():
    """Market with no orderbook returns empty Orderbook."""
    ...

async def test_concurrent_fetch_respects_rate_limit():
    """Semaphore prevents overwhelming the API."""
    ...

async def test_skips_market_on_404():
    """404 still includes market with empty book."""
    ...
```
