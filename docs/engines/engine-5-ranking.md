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
    market: Market
    classification: MarketClassification
    orderbook_stats: MarketOrderbookStats

@dataclass
class EventWithTopMarkets:
    event_ticker: str
    market_count: int
    same_day_live_market_count: int
    total_event_resting_order_quantity: float
    active_orderbook_market_count: int
    top_3_markets_by_current_orders: list[RankedMarket]
    all_same_day_live_markets_ranked: list[RankedMarket]

@dataclass
class Engine5Output:
    events: list[EventWithTopMarkets]
```

## Ranking Metric

### Primary: Total Resting Order Quantity

```python
def compute_orderbook_stats(market: Market, orderbook: Orderbook) -> MarketOrderbookStats:
    yes_qty = sum(level.size for level in orderbook.yes_bids)
    no_qty = sum(level.size for level in orderbook.no_bids)

    return MarketOrderbookStats(
        market_id=market.id,
        event_id=market.event_id,
        total_resting_order_quantity=yes_qty + no_qty,
        yes_order_quantity=yes_qty,
        no_order_quantity=no_qty,
        depth_level_count=len(orderbook.yes_bids) + len(orderbook.no_bids),
        best_yes_bid=orderbook.yes_bids[0].price if orderbook.yes_bids else None,
        best_no_bid=orderbook.no_bids[0].price if orderbook.no_bids else None,
        volume_24h=float(market.volume_24h or 0),
        total_volume=float(market.total_volume or 0),
    )
```

### Sort Order

```python
def rank_markets(markets: list[RankedMarket]) -> list[RankedMarket]:
    """
    Sort by:
    1. total_resting_order_quantity DESC (most active first)
    2. depth_level_count DESC (more depth levels = more activity)
    3. volume_24h DESC (recent trade activity tiebreaker)
    4. total_volume DESC (all-time volume tiebreaker)
    """
    return sorted(
        markets,
        key=lambda m: (
            m.orderbook_stats.total_resting_order_quantity,
            m.orderbook_stats.depth_level_count,
            m.orderbook_stats.volume_24h,
            m.orderbook_stats.total_volume,
        ),
        reverse=True,
    )
```

## Implementation

```python
async def rank_events(engine4_output: Engine4Output) -> Engine5Output:
    """
    For each event, compute orderbook stats and rank markets.
    Returns top 3 + full ranked list for the progress gate.
    """
    ranked_events = []

    for event in engine4_output.events:
        # Compute stats for each market
        markets_with_stats = [
            RankedMarket(
                market=ewb.market,
                classification=ewb.classification,
                orderbook_stats=compute_orderbook_stats(ewb.market, ewb.orderbook),
            )
            for ewb in event.same_day_live_markets
        ]

        # Rank
        ranked = rank_markets(markets_with_stats)

        ranked_events.append(EventWithTopMarkets(
            event_ticker=event.event_ticker,
            market_count=event.market_count,
            same_day_live_market_count=event.same_day_live_market_count,
            total_event_resting_order_quantity=sum(
                rm.orderbook_stats.total_resting_order_quantity for rm in ranked
            ),
            active_orderbook_market_count=sum(
                1 for rm in ranked if rm.orderbook_stats.total_resting_order_quantity > 0
            ),
            top_3_markets_by_current_orders=ranked[:3],
            all_same_day_live_markets_ranked=ranked,
        ))

    return Engine5Output(events=ranked_events)
```

## Important Rules

1. **Never remove an event** at this stage — even events where all markets have zero orders remain in the output. The progress gate (Engine 6) decides candidacy.
2. **Rank, don't filter** — the full ranked list is passed through for the strategy profiles.
3. **`all_same_day_live_markets_ranked`** is the authoritative ordering used by Engine 6 for market selection.
4. **`top_3_markets_by_current_orders`** is a display optimization — the UI shows these as the "featured" markets.

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

- `backend/core/models.py` — `MarketOrderbookStats`, `RankedMarket`

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
