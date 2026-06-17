# Engine 6: Event Progress Threshold + Side Selection Engine

## Purpose

Create an order candidate only after a user-configurable percentage of the event has elapsed. This is the **decision engine** — it determines whether to act on a ranked event.

## Input

```python
@dataclass
class Engine6Input:
    events: list[EventWithTopMarkets]    # From Engine 5 (ranked)
    strategy: StrategyProfile             # Active strategy (configurable)
    threshold_percent: int                # Default: 65
    now: datetime                         # Default: system clock
```

## Output

```python
@dataclass
class ProgressBasedOrderCandidate:
    event_ticker: str
    threshold_percent: int
    event_progress_percent: float
    event_passes_progress_threshold: bool
    selected_market: Market | None
    selected_market_stats: MarketOrderbookStats | None
    most_bet_side: str                    # "yes" | "no" | "tie" | "none"
    yes_order_quantity: float
    no_order_quantity: float
    total_resting_order_quantity: float
    should_create_order_candidate: bool
    requires_manual_review: bool
    reasons: list[str]

@dataclass
class Engine6Output:
    threshold_percent: int
    candidates: list[ProgressBasedOrderCandidate]
    actionable_candidates: list[ProgressBasedOrderCandidate]
    manual_review_candidates: list[ProgressBasedOrderCandidate]
```

## Event Progress Calculation

### Formula

```python
def get_end_time(market: Market) -> datetime | None:
    """Fallback chain for event end time."""
    return (
        parse_date(market.expected_expiration_time)
        or parse_date(market.latest_expiration_time)
        or parse_date(market.close_time)
    )

def calculate_event_progress(market: Market, now: datetime) -> float:
    """
    Calculate what percentage of the event has elapsed.
    Uses the most-bet market as a proxy for the event's timeline.

    Returns 0–100, clamped.
    """
    start = parse_date(market.open_time)
    end = get_end_time(market)

    if not start or not end:
        return 0.0

    total_ms = (end - start).total_seconds() * 1000
    elapsed_ms = (now - start).total_seconds() * 1000

    if total_ms <= 0:
        return 100.0

    raw = (elapsed_ms / total_ms) * 100
    return max(0.0, min(100.0, raw))
```

### End Time Fallback

1. `expected_expiration_time` — primary (most accurate)
2. `latest_expiration_time` — secondary (latest possible)
3. `close_time` — last resort (market closing time)

## Side Selection

The active **strategy profile** handles side selection. The default `MostBetStrategy` uses:

```python
def select_side(self, stats: MarketOrderbookStats) -> str:
    if stats.yes_order_quantity > stats.no_order_quantity:
        return "yes"
    elif stats.no_order_quantity > stats.yes_order_quantity:
        return "no"
    elif stats.total_resting_order_quantity > 0:
        return "tie"    # Manual review required
    return "none"        # No activity
```

See the [Strategy System](strategy-system.md) doc for other profiles.

## Order Candidate Creation Rules

Create a candidate **only if ALL** of:

1. Event progress >= user threshold (default 65%)
2. Selected market exists
3. Selected market still passes `SAME_DAY_LIVE_MARKET` classification
4. Selected market has `total_resting_order_quantity > 0`
5. Most-bet side is `"yes"` or `"no"` (not `"tie"` or `"none"`)

## Implementation

```python
def create_progress_based_candidate(
    event: EventWithTopMarkets,
    strategy: StrategyProfile,
    threshold_percent: int,
    now: datetime,
) -> ProgressBasedOrderCandidate:
    reasons: list[str] = []

    # Step 1: Strategy selects the market
    selected = strategy.select_market(event.all_same_day_live_markets_ranked)
    if not selected:
        reasons.append("No same-day live market exists in event.")
        return empty_candidate(event.event_ticker, threshold_percent, reasons)

    market = selected.market
    stats = selected.orderbook_stats

    # Step 2: Calculate progress
    progress = calculate_event_progress(market, now)
    passes_threshold = progress >= threshold_percent
    if not passes_threshold:
        reasons.append(f"Progress {progress:.2f}% < threshold {threshold_percent}%.")

    # Step 3: Re-check classification
    classification = classify_market(market, now)
    if not classification.same_day_live_market:
        reasons.append("Selected market no longer passes same-day live classification.")

    # Step 4: Check order quantity
    if stats.total_resting_order_quantity <= 0:
        reasons.append("Selected market has no resting order quantity.")

    # Step 5: Strategy selects side
    side = strategy.select_side(selected, stats)
    if side == "tie":
        reasons.append("YES and NO have equal resting order quantity.")
    elif side == "none":
        reasons.append("No most-bet side exists (zero order quantity).")

    should_create = (
        passes_threshold
        and classification.same_day_live_market
        and stats.total_resting_order_quantity > 0
        and side in ("yes", "no")
    )

    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        threshold_percent=threshold_percent,
        event_progress_percent=progress,
        event_passes_progress_threshold=passes_threshold,
        selected_market=market,
        selected_market_stats=stats,
        most_bet_side=side,
        yes_order_quantity=stats.yes_order_quantity,
        no_order_quantity=stats.no_order_quantity,
        total_resting_order_quantity=stats.total_resting_order_quantity,
        should_create_order_candidate=should_create,
        requires_manual_review=(side == "tie"),
        reasons=reasons,
    )


def process_all_events(
    events: list[EventWithTopMarkets],
    strategy: StrategyProfile,
    threshold_percent: int = 65,
    now: datetime | None = None,
) -> Engine6Output:
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    candidates = [
        create_progress_based_candidate(event, strategy, threshold_percent, now)
        for event in events
    ]

    return Engine6Output(
        threshold_percent=threshold_percent,
        candidates=candidates,
        actionable_candidates=[c for c in candidates if c.should_create_order_candidate],
        manual_review_candidates=[c for c in candidates if c.requires_manual_review],
    )
```

## Strategy Integration

Engine 6 receives the active strategy as a dependency. The pipeline wires it:

```python
# In Engine 8 (orchestrator):
strategy = get_strategy(config.strategy.active_profile, config.strategy.profiles)
engine6 = ProgressGateEngine(strategy=strategy, default_threshold=config.strategy.default_threshold)
output = await engine6.process(engine5_output)
```

Strategy profiles are defined in `backend/strategies/`. See [Strategy System](strategy-system.md) for all profiles.

## Non-Global Threshold

The `CustomThresholdStrategy` allows per-event-type thresholds:

```yaml
strategy:
  active_profile: custom-threshold
  profiles:
    custom-threshold:
      per_event_type:
        default: 65
        sports: 50
        politics: 75
```

When this strategy is active, Engine 6 uses the event-specific threshold instead of the global default.

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Event 25% done, threshold 65% | Candidate not created, reason logged |
| Market has YES qty 0, NO qty 0 | `side="none"`, candidate not created |
| YES qty == NO qty (both > 0) | `side="tie"`, requires manual review |
| Market expired between ranking and gate | Re-classify fails, candidate not created |
| Event with 0 markets (shouldn't happen) | Empty candidate with reason |

## Dependencies

- `backend/strategies/` — Active strategy profile
- `backend/core/models.py` — `EventWithTopMarkets`, `ProgressBasedOrderCandidate`
- `backend/engines/engine2_classification.py` — `classify_market()` for re-check

## Testing

```python
async def test_creates_candidate_when_threshold_passed():
    """Progress >= 65% + valid market + valid side → candidate created."""
    ...

async def test_blocks_candidate_below_threshold():
    """Progress < 65% → no candidate, reason logged."""
    ...

async def test_blocks_candidate_when_side_is_tie():
    """YES == NO qty → manual review, no automatic candidate."""
    ...

async def test_blocks_candidate_when_side_is_none():
    """Zero order qty → no candidate."""
    ...

async def test_strategy_plugs_in_correctly():
    """Active strategy's select_market/select_side are called."""
    ...

async def test_custom_threshold_uses_event_type_threshold():
    """CustomThresholdStrategy uses per-event-type threshold."""
    ...
```
