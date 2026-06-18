# Engine 3: Same-Day Live Event Grouping Engine

## Purpose

Group the same-day live markets (from Engine 2) by `event_ticker`. This converts a flat list of classified markets into a structured event view.

## Input

```python
@dataclass
class Engine2Output:
    same_day_live_markets: list[tuple[Market, ClassificationResult]]
```

Where:

```python
from backend.core.models.market import Market
from backend.core.models.classification import ClassificationResult

# Engine 2 returns a flat list of (Market, ClassificationResult) pairs.
# ClassificationResult fields:
#   market_ticker: str
#   event_ticker: str
#   is_same_day_live: bool
#   confidence: float
#   reason: str
```

## Output

```python
@dataclass
class ClassifiedEvent:
    event_ticker: str
    event_title: str
    markets: list[Market]                # All child markets (flat)
    classification: ClassificationResult | None = None
    num_markets: int = 0                 # Count of child markets
    total_volume: int = 0                # Sum of market volumes

@dataclass
class Engine3Output:
    events: list[ClassifiedEvent]
```

## Event Inclusion Rule

```
event qualifies if ANY child market passes SAME_DAY_LIVE_MARKET
```

Do NOT require every child market to pass. A single live market qualifies the entire event.

## Implementation

```python
def group_by_event_ticker(
    same_day_live_markets: list[tuple[Market, ClassificationResult]],
) -> Engine3Output:
    """
    Group same-day live markets by event_ticker.
    An event qualifies if at least one child market is same-day live.
    """
    by_event: dict[str, dict] = {}

    for market, classification in same_day_live_markets:
        ticker = market.event_ticker
        if ticker not in by_event:
            by_event[ticker] = {
                "event_ticker": ticker,
                "event_title": market.title,
                "markets": [],
                "classifications": [],
            }
        by_event[ticker]["markets"].append(market)
        by_event[ticker]["classifications"].append(classification)

    events = []
    for ticker, data in by_event.items():
        markets = data["markets"]
        classifs = data["classifications"]
        total_volume = sum(m.volume for m in markets if isinstance(m.volume, int))

        # Pick the best classification for the event
        best_c = max(classifs, key=lambda c: c.confidence)

        events.append(ClassifiedEvent(
            event_ticker=ticker,
            event_title=markets[0].title if markets else "",
            markets=markets,
            classification=best_c,
            num_markets=len(markets),
            total_volume=total_volume,
        ))

    # Sort by event_ticker for deterministic output
    events.sort(key=lambda e: e.event_ticker)

    return Engine3Output(events=events)
```

## Key Concepts

### Why group by event_ticker?

Kalshi's hierarchy is `Series → Event → Market`. The `event_ticker` links child markets to their parent event. Grouping by it lets us:

1. Show users a consolidated view per real-world occurrence
2. Rank markets within a meaningful context
3. Apply progress gates at the event level

### Why not group by series_ticker?

Events are the unit of real-world occurrences. A Series is a recurring template (e.g., "Will Bitcoin reach $X by date Y"). Markets within a Series may span different days. Grouping by Series would mix same-day and future markets.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Event with 1 same-day live market and 4 non-live markets | Event qualifies, `num_markets=5` |
| Event with 0 same-day live markets | Not included (filtered by Engine 2) |
| Market with no `event_ticker` | Log warning, skip market |
| 100+ markets in one event | All included — no truncation at this stage |

## Dependencies

- `backend.core.models.market` — `Market`
- `backend.core.models.classification` — `ClassificationResult`, `ClassifiedEvent`

## Testing

```python
async def test_groups_by_event_ticker():
    """Markets with same event_ticker end up in same event."""
    ...

async def test_event_qualifies_with_one_live_market():
    """Event qualifies even if only 1 of 5 markets is same-day live."""
    ...

async def test_empty_input_returns_empty():
    """Empty list returns Engine3Output(events=[])."""
    ...

async def test_events_are_deterministic():
    """Same input always produces same ordering."""
    ...
```
