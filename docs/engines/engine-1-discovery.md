# Engine 1: Market Discovery Engine

## Purpose

Fetch all currently open markets from Kalshi. This is the entry point of the pipeline — nothing happens before this engine runs.

## Input

None (or config containing base URL and pagination settings).

## Output

```python
@dataclass
class Engine1Output:
    scanned_market_count: int
    markets: list[Market]
```

## Kalshi Endpoint

```
GET https://api.elections.kalshi.com/trade-api/v2/markets
```

### Request Parameters

| Param | Value | Reason |
|-------|-------|--------|
| `status` | `open` | Only currently open markets |
| `limit` | `1000` | Maximum page size |
| `mve_filter` | `exclude` | Exclude multivariate events |
| `cursor` | *(from previous response)* | Pagination cursor |

## Implementation

```python
async def fetch_all_open_markets(client: MarketReader) -> Engine1Output:
    """
    Fetch all open markets with cursor-based pagination.
    Deduplicates by ticker (in case of cursor overlap).

    Uses MarketReader.fetch_markets(**kwargs) -> list[dict[str, Any]]
    (the actual Kalshi adapter returns raw API dicts; parsing to Market
    dataclasses happens inside the adapter layer).
    """
    all_markets: list[Market] = []
    cursor: str | None = None

    while True:
        params = {"status": "open", "limit": 1000, "mve_filter": "exclude"}
        if cursor:
            params["cursor"] = cursor

        markets_data = await client.fetch_markets(**params)

        all_markets.extend(markets_data)

        # Cursor-based pagination: fetch_markets returns raw API dicts
        # which include a "cursor" key when more pages exist.
        # The adapter handles cursor extraction internally.
        if not markets_data:
            break

    # Deduplicate by ticker (safety net for pagination edge cases)
    unique = {m.ticker: m for m in all_markets}

    return Engine1Output(
        scanned_market_count=len(unique),
        markets=list(unique.values()),
    )
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| HTTP 429 (rate limit) | Exponential backoff, retry up to 3 times |
| HTTP 5xx | Retry once, then fail (the adapter should define its own error hierarchy; Phase 1 uses httpx status checks) |
| Network timeout | Retry once, then fail (forward-looking — Phase 1 adapter raises on httpx timeout) |
| Empty response | Return `Engine1Output(scanned_market_count=0, markets=[])` |
| Partial data (some markets malformed) | Log warning, skip malformed entries, continue |

## Non-Negotiable Rules

1. Must use cursor pagination — do not assume a single page covers all markets.
2. Must deduplicate by `ticker` — cursors may return overlapping results.
3. Must not filter by category, keyword, volume, or any other signal. Return **all** open markets.
4. Must set reasonable timeout (30s recommended for initial fetch).

## Dependencies

- `backend/core/interfaces/adapter.py` — `MarketReader` (the interface this engine depends on)
- `backend.core.models.market` — `Market` dataclass

## Testing

```python
# Unit tests (using a mock MarketReader)
async def test_deduplicates_by_ticker():
    ...

async def test_handles_empty_response():
    ...

async def test_handles_pagination():
    ...

async def test_retries_on_rate_limit():
    ...
```
