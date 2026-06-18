# Engine 5: Top Markets By Current Orders Ranking Engine

## Purpose

Rank markets inside each event by current resting order activity. This answers: *"Which markets inside this event currently have the most bidding activity?"*

## Input

```python
@dataclass
class Engine5Input:
    events: list[EventWithOrderbooks]    # From Engine 4
```

## Output

```python
@dataclass
class RankedMarket:
    market_ticker: str
    volume: int
    spread_cents: int
    yes_price: int
    no_price: int
    rank: int
    score: float

@dataclass
class EventWithTopMarkets:
    event_ticker: str
    event_title: str
    top_markets: list[RankedMarket] = field(default_factory=list)
    total_volume: int = 0
    num_top_markets: int = 0

@dataclass
class Engine5Output:
    events: list[EventWithTopMarkets]
```

## Ranking Metric

### Primary: Total Resting Order Quantity

```python
def compute_orderbook_stats(market: Market, orderbook: Orderbook) -> MarketOrderbookStats:
    yes_qty = sum(level.count for level in orderbook.yes_side)
    no_qty = sum(level.count for level in orderbook.no_side)

    return MarketOrderbookStats(
        market_ticker=market.ticker,
        event_ticker=market.event_ticker,
        total_resting_order_quantity=yes_qty + no_qty,
        best_yes_bid=orderbook.yes_side[0].price if orderbook.yes_side else None,
        best_no_bid=orderbook.no_side[0].price if orderbook.no_side else None,
        volume_24h=market.volume_24h or 0,
    )
```

### Sort Order

```python
def rank_markets(markets: list[RankedMarket]) -> list[RankedMarket]:
    """
    Sort by:
    1. volume DESC (most volume first)
    2. spread_cents ASC (tighter spread = more active)
    3. score DESC (composite ranking score tiebreaker)
    """
    return sorted(
        markets,
        key=lambda m: (
            -m.volume,
            m.spread_cents,
            -m.score,
        ),
    )
```

## Implementation

```python
async def rank_events(engine4_output: Engine4Output) -> Engine5Output:
    """
    For each event, compute orderbook stats and rank markets.
    Returns top markets for the progress gate.
    """
    ranked_events = []

    for event in engine4_output.events:
        # Compute stats for each market
        markets_with_stats = []
        for ewb in event.same_day_live_markets:
            stats = compute_orderbook_stats(ewb.market, ewb.orderbook)
            markets_with_stats.append(RankedMarket(
                market_ticker=ewb.market.ticker,
                volume=ewb.market.volume,
                spread_cents=stats.spread_cents or 0,
                yes_price=ewb.market.yes_bid or 0,
                no_price=ewb.market.no_bid or 0,
                rank=0,
                score=0.0,
            ))

        # Rank
        ranked = rank_markets(markets_with_stats)
        # Re-assign ranks after sorting
        for i, rm in enumerate(ranked):
            rm.rank = i + 1
            rm.score = rm.volume  # Simple score = volume

        ranked_events.append(EventWithTopMarkets(
            event_ticker=event.event_ticker,
            event_title="",
            top_markets=ranked,
            total_volume=sum(rm.volume for rm in ranked),
            num_top_markets=len(ranked),
        ))

    return Engine5Output(events=ranked_events)
```

## Important Rules

1. **Never remove an event** at this stage — even events where all markets have zero volume remain in the output. The progress gate (Engine 6) decides candidacy.
2. **Rank, don't filter** — the full ranked list is passed through for the strategy profiles.
3. **`top_markets`** is the authoritative ordering used by Engine 6 for market selection.
4. **`top_markets[:3]`** is a display optimization — the UI shows these as the "featured" markets.

## Example

Given event EVTA with 3 markets:

| Market | YES qty | NO qty | Total | Depth | Vol 24h |
|--------|---------|--------|-------|-------|---------|
| EVTA-M2 | 50 | 100 | **150** | 12 | $300 |
| EVTA-M1 | 80 | 20 | **100** | 8 | $500 |
| EVTA-M3 | 0 | 0 | **0** | 0 | $900 |

Ranked:
1. EVTA-M2 (total=150, depth=12)
2. EVTA-M1 (total=100, depth=8)
3. EVTA-M3 (total=0, depth=0 — tiebreaker by volume alone doesn't help)

## Dependencies

- `backend.core.models.market` — `Market`, `Orderbook`, `MarketOrderbookStats`
- `backend.core.models.trading` — `RankedMarket`, `EventWithTopMarkets`

## Testing

```python
async def test_ranks_by_total_quantity_first():
    """Market with higher total order quantity ranks first."""
    ...

async def test_uses_depth_level_as_tiebreaker():
    """Same total qty → higher depth level count wins."""
    ...

async def test_uses_24h_volume_as_second_tiebreaker():
    """Same qty + depth → higher 24h volume wins."""
    ...

async def test_includes_markets_with_zero_orders():
    """Markets with zero orders remain in ranked list."""
    ...

async def test_empty_event_returns_empty_rankings():
    """Event with no markets returns empty lists."""
    ...
```
