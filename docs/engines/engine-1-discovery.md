# Engine 1: Market Discovery Engine

## Purpose

Fetch all currently open markets from Kalshi. This is the entry point of the pipeline — nothing happens before this engine runs.

## Input

None (or config containing base URL and pagination settings).

## Output

```python
# Returns: list[Market] (not an Engine1Output wrapper — the pipeline
# uses simple types. The scanned count is tracked by the caller.)
```

## Kalshi Endpoint

```
GET https://api.elections.kalshi.com/trade-api/v2/markets
```

Pagination is handled internally by the adapter layer (see `KalshiClient.fetch_all_open_markets()`). The engine calls `adapter.get_all_open_markets()` which returns fully parsed `Market` domain objects.

## Implementation

```python
async def fetch_all_open_markets(adapter: KalshiAdapter) -> list[Market]:
    """
    Fetch all open markets using the adapter's internal pagination.
    The adapter handles cursor-based pagination internally.
    Returns parsed Market domain objects.
    """
    markets = await adapter.get_all_open_markets()
    logger.info("Fetched %d open markets.", len(markets))
    return markets
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| HTTP 429 (rate limit) | Exponential backoff, retry up to 3 times |
| HTTP 5xx | Retry once, then fail (the adapter should define its own error hierarchy; Phase 1 uses httpx status checks) |
| Network timeout | Retry once, then fail (adapter raises on httpx timeout) |
| Empty response | Return `[]` |
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
