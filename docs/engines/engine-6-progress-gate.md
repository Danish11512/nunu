# Engine 6: Event Progress Threshold + Side Selection Engine

## Purpose

Create an order candidate only after a user-configurable percentage of the event has elapsed. This is the **decision engine** — it determines whether to act on a ranked event.

## Input

```python
@dataclass
class Engine6Input:
    events: list[EventWithTopMarkets]    # From Engine 5 (ranked)
    strategy: StrategyProfile             # Active strategy (configurable)
    threshold_percent: float              # Default: 0.60
    now: datetime                         # Default: system clock
```

## Output

```python
@dataclass
class ProgressBasedOrderCandidate(OrderCandidate):
    """Candidate created by Engine 6 (progress gate)."""
    most_bet_side: str = ""       # "yes" / "no" — the side with most betting activity
    threshold_pct: float = 0.0     # The threshold that was met
    is_overtime: bool = False      # Whether the event is in overtime
    # Note: progress_pct inherited from OrderCandidate (0-100 scale)

@dataclass
class Engine6Output:
    threshold_percent: float
    candidates: list[ProgressBasedOrderCandidate]
    actionable_candidates: list[ProgressBasedOrderCandidate]
```

## Event Progress Calculation

### Formula

`calculate_progress` from `backend.utils.datetime_utils` is used:

```python
from backend.utils.datetime_utils import calculate_progress, parse_date

def calculate_event_progress(market: Market, now: datetime) -> float:
    """
    Calculate what percentage of the event has elapsed.

    Returns 0–100, clamped.
    """
    expires_at = market.expiry
    start_at = parse_date(market.create_date)

    return calculate_progress(expires_at, now, start_at) if expires_at else 0.0
```

### End Time

Uses `market.expiry` (expected_expiration_time from API, parsed to datetime).

## Side Selection

The active **strategy** handles market and side selection via a single
`select_trade()` call. The default `favorite-side-follower` uses
volume and bid/ask prices to determine which side to favor:

```python
def select_trade(self, event_features: EventFeatures) -> TradeDecision:
    valid = [m for m in event_features.child_markets if m.volume > 0]
    if not valid:
        return TradeDecision(market_ticker="", side=None, should_trade=False, reason="no_markets_with_volume")

    selected = max(valid, key=lambda m: m.volume)
    side = "yes" if selected.yes_bid > selected.no_bid else "no"
    return TradeDecision(market_ticker=selected.ticker, side=side, should_trade=True, ...)
```

See the [Strategy System](strategy-system.md) doc for all profiles.

## Order Candidate Creation Rules

Create a candidate **only if ALL** of:

1. Event progress >= user threshold (default 60%)
2. Strategy returns `should_trade == True`
3. Selected market still passes `SAME_DAY_LIVE_MARKET` classification
4. Selected side is `"yes"` or `"no"`

## Implementation

```python
def create_progress_based_candidate(
    event: EventWithTopMarkets,
    strategy: StrategyProfile,
    threshold_percent: float,
    now: datetime,
    child_market_features: list[MarketFeatures],
) -> ProgressBasedOrderCandidate:
    reasons: list[str] = []

    # Build EventFeatures for the strategy
    event_features = EventFeatures(
        event_ticker=event.event_ticker,
        event_title=event.event_title,
        child_markets=child_market_features,
    )

    # Step 1: Strategy selects market + side in a single call
    decision = strategy.select_trade(event_features)

    if not decision.should_trade:
        reasons.append(decision.reason or "Strategy returned no trade.")
        return empty_candidate(event.event_ticker, threshold_percent, reasons)

    # Step 2: Calculate progress
    top_market = event.top_markets[0] if event.top_markets else None
    progress = calculate_event_progress(top_market, now) if top_market else 0.0
    passes_threshold = progress >= threshold_percent
    if not passes_threshold:
        reasons.append(f"Progress {progress:.2f}% < threshold {threshold_percent}%.")

    # Step 3: Re-check classification
    selected_market_data = next(
        (rm for rm in event.top_markets if rm.market_ticker == decision.market_ticker),
        None,
    )
    classification = classify_market(selected_market_data, now) if selected_market_data else None
    if classification and not classification.is_same_day_live:
        reasons.append("Selected market no longer passes same-day live classification.")

    should_create = (
        passes_threshold
        and classification is not None and classification.is_same_day_live
        and decision.should_trade
    )

    return ProgressBasedOrderCandidate(
        event_ticker=event.event_ticker,
        market_ticker=decision.market_ticker,
        side=decision.side,
        price=decision.entry_price_cents,
        confidence=decision.confidence,
        reason="; ".join(reasons),
        volume=decision.max_contracts,
        progress_pct=progress,
        threshold_pct=threshold_percent,
        most_bet_side=decision.side or "",
        is_overtime=False,
    )


def process_all_events(
    events: list[EventWithTopMarkets],
    strategy: StrategyProfile,
    threshold_percent: float = 0.60,
    now: datetime | None = None,
    feature_builder=None,
) -> Engine6Output:
    if now is None:
        now = datetime.now(ZoneInfo("America/New_York"))

    candidates = []
    for event in events:
        # Build market features for each child market
        child_features = []
        for rm in event.top_markets:
            mf = feature_builder(rm, now) if feature_builder else MarketFeatures(
                ticker=rm.market_ticker,
                volume=rm.volume,
                spread_cents=rm.spread_cents,
                yes_bid=rm.yes_price,
                no_bid=rm.no_price,
            )
            child_features.append(mf)

        candidate = create_progress_based_candidate(
            event, strategy, threshold_percent, now, child_features,
        )
        candidates.append(candidate)

    return Engine6Output(
        threshold_percent=threshold_percent,
        candidates=candidates,
        actionable_candidates=[c for c in candidates if c.side in ("yes", "no") and c.confidence > 0],
    )
```
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
| Market has no volume | `side=None`, candidate not created |
| Strategy returns `should_trade=False` | Candidate not created, reason logged |
| Market expired between ranking and gate | Re-classify fails, candidate not created |
| Event with 0 markets (shouldn't happen) | Empty candidate with reason |

## Dependencies

- `backend/strategies/` — Active strategy profile
- `backend.core.models.trading` — `EventWithTopMarkets`, `OrderCandidate`, `ProgressBasedOrderCandidate`
- `backend.core.models.classification` — `ClassificationResult`
- `backend.core.interfaces.strategy` — `StrategyProfile`, `EventFeatures`, `MarketFeatures`, `TradeDecision`
- `backend.utils.datetime_utils` — `calculate_progress`, `parse_date`

## Testing

```python
async def test_creates_candidate_when_threshold_passed():
    """Progress >= 65% + valid market + valid side → candidate created."""
    ...

async def test_blocks_candidate_below_threshold():
    """Progress < 65% → no candidate, reason logged."""
    ...

async def test_blocks_candidate_when_strategy_returns_no_trade():
    """Strategy returns should_trade=False → no candidate."""
    ...

async def test_blocks_candidate_when_market_expired():
    """Market expired between ranking and gate → re-classify fails."""
    ...

async def test_strategy_plugs_in_correctly():
    """Active strategy's select_trade() is called."""
    ...

async def test_custom_threshold_uses_event_type_threshold():
    """CustomThresholdStrategy uses per-event-type threshold."""
    ...
```
