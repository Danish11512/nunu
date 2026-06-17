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
@dataclass
class MarketWithOrderbook:
    market: Market
    classification: MarketClassification
    orderbook: Orderbook

@dataclass
class EventWithOrderbooks:
    event_ticker: str
    market_count: int
    same_day_live_market_count: int
    same_day_live_markets: list[MarketWithOrderbook]

@dataclass
class Engine4Output:
    events: list[EventWithOrderbooks]
```

## Kalshi Endpoint

```
GET https://external-api.kalshi.com/trade-api/v2/markets/{ticker}/orderbook
```

### Response Format

Kalshi orderbooks return **bids only** for each outcome token:

```json
{
  "orderbook_fp": {
    "yes_dollars": [["0.65", "1000"], ["0.64", "500"], ...],
    "no_dollars":  [["0.35", "800"], ["0.34", "300"], ...]
  }
}
```

Each level is `[price_dollars, count_fp]` — a string tuple.

### Orderbook Semantics (Kalshi)

- `yes_dollars` = bids for the YES outcome (people offering to buy YES)
- `no_dollars` = bids for the NO outcome (people offering to buy NO)
- Kalshi does **not** directly expose asks in the orderbook endpoint
- For ranking purposes, we use resting bid quantities directly

## Implementation

```python
async def fetch_orderbooks(events: list[ClassifiedEvent], client: KalshiClient) -> Engine4Output:
    """
    Fetch orderbooks for all same-day live markets across all events.
    Markets with no orderbook data are still included (empty orderbook).
    """
    result_events = []

    for event in events:
        markets_with_books = []

        for cm in event.same_day_live_markets:
            try:
                orderbook = await client.get_orderbook(cm.market.ticker)
            except OrderbookNotFoundError:
                # Market has no orderbook yet — still include it
                orderbook = Orderbook(market_id=cm.market.ticker)
            except Exception:
                # Network error — log and continue with empty book
                logger.warning(f"Failed to fetch orderbook for {cm.market.ticker}")
                orderbook = Orderbook(market_id=cm.market.ticker)

            markets_with_books.append(MarketWithOrderbook(
                market=cm.market,
                classification=cm.classification,
                orderbook=orderbook,
            ))

        result_events.append(EventWithOrderbooks(
            event_ticker=event.event_ticker,
            market_count=event.market_count,
            same_day_live_market_count=event.same_day_live_market_count,
            same_day_live_markets=markets_with_books,
        ))

    return Engine4Output(events=result_events)
```

## Orderbook Parsing

```python
def parse_orderbook_levels(
    yes_dollars: list[tuple[str, str]] | None,
    no_dollars: list[tuple[str, str]] | None,
) -> tuple[list[OrderbookLevel], list[OrderbookLevel]]:
    """Parse Kalshi FP string tuples into OrderbookLevel objects."""

    def parse_levels(levels: list[tuple[str, str]] | None) -> list[OrderbookLevel]:
        if not levels:
            return []
        return [
            OrderbookLevel(price=float(price), size=float(count))
            for price, count in levels
        ]

    return (
        parse_levels(yes_dollars),
        parse_levels(no_dollars),
    )
```

## Concurrency

Fetch orderbooks **concurrently** — don't serialize. Kalshi has rate limits, so use a bounded semaphore:

```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

async def fetch_with_limit(ticker: str) -> Orderbook:
    async with semaphore:
        return await client.get_orderbook(ticker)
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

- `backend/adapters/kalshi/client.py` — `KalshiClient.get_orderbook()`
- `backend/core/models.py` — `Orderbook`, `OrderbookLevel`

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
