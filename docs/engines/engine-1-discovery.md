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
GET https://external-api.kalshi.com/trade-api/v2/markets
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
async def fetch_all_open_markets(client: KalshiClient) -> Engine1Output:
    """
    Fetch all open markets with cursor-based pagination.
    Deduplicates by ticker (in case of cursor overlap).
    """
    all_markets: list[Market] = []
    cursor: str | None = None

    while True:
        params = {"status": "open", "limit": 1000, "mve_filter": "exclude"}
        if cursor:
            params["cursor"] = cursor

        response = await client.get("/markets", params=params)
        data = response.json()

        all_markets.extend(data.get("markets", []))

        cursor = data.get("cursor")
        if not cursor:
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
| HTTP 5xx | Retry once, then fail with `KalshiServerError` |
| Network timeout | Retry once, then fail with `KalshiNetworkError` |
| Empty response | Return `Engine1Output(scanned_market_count=0, markets=[])` |
| Partial data (some markets malformed) | Log warning, skip malformed entries, continue |

## Non-Negotiable Rules

1. Must use cursor pagination — do not assume a single page covers all markets.
2. Must deduplicate by `ticker` — cursors may return overlapping results.
3. Must not filter by category, keyword, volume, or any other signal. Return **all** open markets.
4. Must set reasonable timeout (30s recommended for initial fetch).

## Dependencies

- `backend/adapters/kalshi/client.py` — `KalshiClient` with rate limiting and error handling
- `backend/core/models.py` — `Market` dataclass

## Testing

```python
# Unit tests
async def test_deduplicates_by_ticker():
    ...

async def test_handles_empty_response():
    ...

async def test_handles_pagination():
    ...

async def test_retries_on_rate_limit():
    ...
```
