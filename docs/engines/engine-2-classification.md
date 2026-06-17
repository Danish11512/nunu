# Engine 2: Same-Day Live Market Classification Engine

## Purpose

Classify which markets are currently live and will resolve today. This is the **gatekeeper** — only markets passing this engine proceed to grouping, orderbook fetching, and ranking.

## Input

```python
@dataclass
class Engine2Input:
    markets: list[Market]    # All open markets from Engine 1
    now: datetime            # Reference time (default: system clock)
```

## Output

```python
@dataclass
class MarketClassification:
    ticker: str
    event_ticker: str
    live_now: bool
    expected_to_resolve_today: bool
    latest_expiration_today: bool
    same_day_live_market: bool
    reasons: list[str]

@dataclass
class Engine2Output:
    classified_markets: list[tuple[Market, MarketClassification]]
    same_day_live_markets: list[tuple[Market, MarketClassification]]  # filtered
```

## Classification Rule (Kalshi)

```
SAME_DAY_LIVE_MARKET =
    market.status == "open"
    AND market.open_time <= now
    AND market.close_time > now
    AND expected_expiration_time is today in America/New_York
    AND latest_expiration_time is today in America/New_York
```

### Field Mappings (Kalshi)

| Rule | Kalshi Field | Type | Notes |
|------|-------------|------|-------|
| Status check | `status` | string | Must equal `"open"` |
| Open time | `open_time` | ISO 8601 | Must be in the past |
| Close time | `close_time` | ISO 8601 | Must be in the future |
| Expected expiration | `expected_expiration_time` | ISO 8601 | Must be today ET |
| Latest expiration | `latest_expiration_time` | ISO 8601 | Must be today ET |

### Timezone Handling

All "today" comparisons use `America/New_York`:

```python
def day_key_et(date: datetime) -> str:
    """Returns 'YYYY-MM-DD' for the date in America/New_York."""
    return date.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

def same_et_day(a: datetime, b: datetime) -> bool:
    return day_key_et(a) == day_key_et(b)
```

### Expiration Field Deprecation

`expiration_time` is **deprecated**. Always use `expected_expiration_time` and `latest_expiration_time`. If a market only has `expiration_time`, it does **not** pass classification.

## Implementation

```python
def classify_market(market: Market, now: datetime) -> MarketClassification:
    reasons: list[str] = []

    open_time = parse_date(market.open_time)
    close_time = parse_date(market.close_time)
    expected_exp = parse_date(market.expected_expiration_time)
    latest_exp = parse_date(market.latest_expiration_time)

    # Rule 1: Status == "open" and within time bounds
    live_now = (
        market.status == "open"
        and open_time is not None
        and close_time is not None
        and open_time <= now
        and close_time > now
    )
    if not live_now:
        reasons.append("Market is not currently open/live.")

    # Rule 2: Expected expiration is today
    expected_today = (
        expected_exp is not None
        and same_et_day(expected_exp, now)
    )
    if not expected_today:
        reasons.append("Expected expiration is not today ET.")

    # Rule 3: Latest expiration is today
    latest_today = (
        latest_exp is not None
        and same_et_day(latest_exp, now)
    )
    if not latest_today:
        reasons.append("Latest expiration is not today ET.")

    same_day_live = live_now and expected_today and latest_today

    return MarketClassification(
        ticker=market.ticker,
        event_ticker=market.event_ticker,
        live_now=live_now,
        expected_to_resolve_today=expected_today,
        latest_expiration_today=latest_today,
        same_day_live_market=same_day_live,
        reasons=reasons,
    )


def get_same_day_live_markets(
    markets: list[Market],
    now: datetime | None = None,
) -> Engine2Output:
    """Classify all markets and return both full and filtered results."""
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    classified: list[tuple[Market, MarketClassification]] = []
    live: list[tuple[Market, MarketClassification]] = []

    for market in markets:
        classification = classify_market(market, now)
        classified.append((market, classification))
        if classification.same_day_live_market:
            live.append((market, classification))

    return Engine2Output(
        classified_markets=classified,
        same_day_live_markets=live,
    )
```

## Non-Negotiable Rules

1. **Do NOT filter by orderbook** — volume, liquidity, spread, depth are irrelevant here.
2. **Do NOT filter by category or keyword** — no allowlists, no topic filters.
3. **Do NOT classify event status directly** — always classify markets first.
4. **All "today" comparisons use America/New_York** — ET is the market's home timezone.
5. **Treat `expiration_time` as deprecated** — require the two newer fields.

## Why Not Filter?

This engine must be maximally inclusive. A market that passes today but has zero orders now is still a valid same-day live market. It may get orders later, or serve as context for other markets in the same event. Filtering at this stage would create blind spots.

## Edge Cases

| Scenario | Classification | Reason |
|----------|---------------|--------|
| Market opened 1 hour ago, closes in 8 hours, expires today | ✅ SAME_DAY_LIVE | All conditions met |
| Market opened yesterday, closes tomorrow, expected to expire today | ✅ Still same-day live if close_time > now | Only need close in future |
| Market with `close_time` already past | ❌ `live_now=false` | Market is no longer accepting orders |
| Market with `expected_expiration_time` tomorrow | ❌ `expected_today=false` | Won't resolve today |
| Market with `latest_expiration_time` tomorrow (even if expected is today) | ❌ `latest_today=false` | Latest expiration must also be today |
| Market missing `expected_expiration_time` | ❌ `expected_today=false` | Required field |
| Market at exactly midnight ET | ✅ If times include that boundary | Both dates are "today" |

## Dependencies

- `backend/core/models.py` — `Market`, `MarketClassification`
- `zoneinfo` (Python 3.9+) — `ZoneInfo("America/New_York")`

## Testing

```python
async def test_classifies_same_day_live():
    """Market open now, closing later, expiring today → SAME_DAY_LIVE."""
    ...

async def test_excludes_closed_market():
    """Market with close_time in the past → NOT same-day live."""
    ...

async def test_excludes_future_expiration():
    """Market with expected_expiration_time tomorrow → NOT same-day live."""
    ...

async def test_excludes_deprecated_expiration_only():
    """Market with only expiration_time (not expected/latest) → NOT same-day live."""
    ...

async def test_does_not_filter_by_orderbook():
    """Market with zero orderbook qty still passes if lifecycle qualifies."""
    ...

async def test_uses_america_new_york():
    """Comparison respects ET timezone boundary."""
    ...
```
